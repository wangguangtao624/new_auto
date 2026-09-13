#ifndef MAT_FW_HANDLER_H
#define MAT_FW_HANDLER_H
#include <stdint.h>
#include <stddef.h>

#if defined(_WIN32)
  #if defined(MAT_FW_EXPORTS)
    #define MAT_FW_API __declspec(dllexport)
  #else
    #define MAT_FW_API __declspec(dllimport)
  #endif
#else
  #define MAT_FW_API
#endif

#ifdef __cplusplus
extern "C" {
#endif


/* =========================
 *  Status enum
 * ========================= */
typedef enum MatFwHandleStatus {
    FW_STATUS_NONE  = 0,
    FW_STATUS_IN_PROGRESS,
    FW_STATUS_SUCCESS,
    FW_STATUS_FAILED,
    FW_STATUS_CANCELED
} MatFwHandleStatus;

/* =========================
 *  Errorcode
 * ========================= */
typedef enum MatFwHandleError {
    FW_OK = 0,
    FW_ERR_INVALID_PARAM  = -1,
    FW_ERR_OPEN_INI       = -2,
    FW_ERR_OPEN_FW        = -3,
    FW_ERR_IN_PROGRESS    = -4,
    FW_ERR_OPEN_DEVICE    = -5,
    FW_ERR_COMM_DEVICE    = -6,
    FW_ERR_FW_MATCH       = -7,
    FW_ERR_FW_BURN_MODE   = -8,
    FW_ERR_FW_TRANS       = -9,
    FW_ERR_SET_ADDR       = -10,
    FW_ERR_SET_MULTI_ADDR = -11,
    FW_ERR_DISABLED_ALOG  = -12,
    FW_ERR_INTERNAL       = -100
} MatFwHandleError;

/* ==============================
 *  Callback definition
 * ============================== */
/**
 * @param status     Current status
 * @param progress   Progress [0,100], not started the value is -1
 * @param err        errorcode, success the value is FW_OK
 */
typedef void (*MatFwHandleCallback)(
    MatFwHandleStatus status,
    int          progress,
    MatFwHandleError   err
);

/* ==================================
 *  Download Interface
 * ================================== */

/**
 * @brief Startup firmware download
 *
 * @param ini_path   ini configuration file path
 * @param fw_path    Firmware file path
 * @param cb         Callback function
 *
 * @return 0：Download task started successfully
 *         -1：invalid param
 *         -2: open ini file failed
 *         -3: open firmware file failed
 *         -100: Internal error
 */
MAT_FW_API int MatFwDownload(const char* ini_path, const char* fw_path, MatFwHandleCallback cb);


/* ==================================
 *  Upload Interface
 * ================================== */

/**
 * @brief Startup firmware upload
 *
 * @param ini_path   ini configuration file path
 * @param addr       Start address for upload
 * @param length     Length of data to upload
 * @param data       [out] Pointer to buffer that receives uploaded data
 * @param cb         Callback function for upload status
 *
 * @return 0：Upload task started successfully
 *         -1：invalid param
 *         -2: open ini file failed
 *         -100: Internal error
 */
MAT_FW_API int MatFwUpload(const char* ini_path, uint32_t addr, uint32_t length, uint8_t* data, MatFwHandleCallback cb);


#ifdef __cplusplus
}
#endif

#endif /* MAT_FW_HANDLER_H */
