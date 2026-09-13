#ifndef TESTDEVICEEXPORT_H
#define TESTDEVICEEXPORT_H
#include <cstdint>
#ifdef __cplusplus
extern "C" {
#endif
#ifndef TESTLIB_DLL_EXPORT
    #define  TESTLIB_DLL_EXPORT __declspec(dllexport)
#endif

/* ==== QT Environment Initialization ==== */

/**
 * @brief Initializes Qt application environment
 * @note Must be called before any other functions. Not thread-safe.
 */
TESTLIB_DLL_EXPORT void init_qt();

/* ==== Device Basic Operations ==== */

/**
 * @brief Acquires device handle by name
 * @param device_name Null-terminated device identifier string
 * @return Device handle on success, NULL on failure
 * @warning Returned handle must be released with release_device()
 */
TESTLIB_DLL_EXPORT void* get_device(const char* device_name);

/**
 * @brief Releases device resources
 * @param device Handle obtained from get_device()
 */
TESTLIB_DLL_EXPORT void release_device(void* device);

/* ==== Dothinkey Channel Control ==== */

/**
 * @brief Gets Dothinkey currently focused channel name
 * @param device_channel_name [out] Output buffer (min 256 bytes)
 */
TESTLIB_DLL_EXPORT void get_device_focus_channel(char* device_channel_name);

/**
 * @brief Sets Dothinkey focus channel
 * @param device_channel_name Target channel name string
 * @return true on success, false on failure
 */
TESTLIB_DLL_EXPORT bool set_device_focus_channel(const char* device_channel_name);

/* ==== Device I/O Operations ==== */

/**
 * @brief Establishes device connection,
 * @param device Valid device handle
 * @return true on success, false on failure
 */
TESTLIB_DLL_EXPORT bool device_open(void* device);

/**
 * @brief Terminates device connection
 * @param device Valid device handle
 */
TESTLIB_DLL_EXPORT void device_close(void* device);

/**
 * @brief set Dothinkey init configuration
 * @param device Valid device handle
 * @param command Null-terminated configuration string
 */
TESTLIB_DLL_EXPORT void device_setConfigure(void* device, const char* command);

/* ==== sensor Stream Control ==== */

/**
 * @brief Enables sensor video streaming
 * @param device Valid device handle
 * @return true on success, false on failure
 */
TESTLIB_DLL_EXPORT bool device_open_video(void* device);

/**
 * @brief Disables video streaming
 * @param device Valid device handle
 * @return true on success, false on failure
 */
TESTLIB_DLL_EXPORT bool device_close_video(void* device);

/**
 * @brief Stops active video transmission
 * @param device Valid device handle
 * @return true on success, false on failure
 */
TESTLIB_DLL_EXPORT bool device_stop_streaming(void* device);

/**
 * @brief Captures single video frame
 * @param device Valid device handle
 * @return true on success, false on failure
 */
TESTLIB_DLL_EXPORT bool device_grab_one_frame(void* device);

TESTLIB_DLL_EXPORT bool device_grab_one_frame_save(void* device, const char* savePath, const char* fileName);

TESTLIB_DLL_EXPORT bool device_get_fps(void* device, float* fps);

TESTLIB_DLL_EXPORT bool device_get_current_DN(void* device, float* DN);

/* ==== Sensor I2C Bus Operations ==== */

/**
 * @brief Performs I2C read operation
 * @param device Valid device handle
 * @param slaveID 7-bit slave device address
 * @param address Register address
 * @param result [out] Read result storage
 * @param addrlength Address length Data width (8/16/32)
 * @param dataSize Data width (8/16/32)
 * @return true on success, false on failure
 */
TESTLIB_DLL_EXPORT bool device_I2C_Read(void* device, uint8_t slaveID,
                              uint32_t address, uint32_t *result, int addrlength, int dataSize);

/**
 * @brief Performs I2C write operation
 * @param device Valid device handle
 * @param slaveID 7-bit slave device address
 * @param address Register address
 * @param value Data to write
 * @param addrlength Address length Data width (8/16/32)
 * @param dataSize Data width (8/16/32)
 * @return true on success, false on failure
 */
TESTLIB_DLL_EXPORT bool device_I2C_Write(void* device, uint8_t slaveID,
                               uint32_t address, uint32_t value, int addrlength, int dataSize);

/* ==== Switcher Control ==== */

/**
 * @brief Creates switcher instance for serial port
 * @param port_Name Serial port name (e.g., "COM3")
 * @return Switcher handle on success, NULL on failure
 */
TESTLIB_DLL_EXPORT void* get_switcher(const char* port_Name);

/**
 * @brief Establishes switcher connection
 * @param switcher Valid switcher handle
 * @return true on success, false on failure
 */
TESTLIB_DLL_EXPORT bool switcher_open(void* switcher);

/**
 * @brief Terminates switcher connection
 * @param switcher Valid switcher handle
 * @return true on success, false on failure
 */
TESTLIB_DLL_EXPORT bool switcher_close(void* switcher);

/**
 * @brief Activates specified channel
 * @param switcher Valid switcher handle
 * @param channel Zero-based channel index
 * @return true on success, false on failure
 */
TESTLIB_DLL_EXPORT bool switcher_open_channel(void* switcher, int channel);

/**
 * @brief Deactivates specified channel
 * @param switcher Valid switcher handle
 * @param channel Zero-based channel index
 * @return true on success, false on failure
 */
TESTLIB_DLL_EXPORT bool switcher_close_channel(void* switcher, int channel);

/* ==== Firmware Operations ==== */

/**
 * @brief Initiates SOC reboot
 * @param device Valid device handle
 * @param needConfirm Requires confirmation response when true
 * @return true on success, false on failure
 */
TESTLIB_DLL_EXPORT bool firmware_socReboot(void* device, bool needConfirm = true);

/**
 * @brief Configures firmware start address
 * @param device Valid device handle
 * @param startAddress Memory start address
 * @param needConfirm Requires confirmation response when true
 * @return true on success, false on failure
 */
TESTLIB_DLL_EXPORT bool firmware_set_start_address(void* device, uint32_t startAddress, bool needConfirm = true);

/**
 * @brief Finalizes firmware update process
 * @param firmware Valid firmware handle
 * @return true on success, false on failure
 */
TESTLIB_DLL_EXPORT bool firmware_set_update_end(void* firmware);

/**
 * @brief Erases flash memory region
 * @param firmware Valid firmware handle
 * @param startAddress Sector-aligned start address
 * @param endAddress Sector-aligned end address
 * @return true on success, false on failure
 * @note Addresses must align with flash sector boundaries
 */
TESTLIB_DLL_EXPORT bool firmware_earse_flash(void* firmware, uint32_t startAddress, uint32_t endAddress);

/**
 * @brief Defines flash operation region
 * @param firmware Valid firmware handle
 * @param startAddress Start address
 * @param endAddress End address
 * @return true on success, false on failure
 */
TESTLIB_DLL_EXPORT bool firmware_flash_set(void* firmware, uint32_t startAddress, uint32_t endAddress);

/**
 * @brief Performs CRC verification of flash region
 * @param firmware Valid firmware handle
 * @param startAddress Start address
 * @param endAddress End address
 * @param crcValue [out] CRC result storage
 * @return true on success, false on failure
 */
TESTLIB_DLL_EXPORT bool firmware_flash_crc_check(void* firmware, uint32_t startAddress, uint32_t endAddress, uint32_t* crcValue);

/**
 * @brief Writes data to flash memory
 * @param firmware Valid firmware handle
 * @param data Binary data to write
 * @param dataSize Data length in bytes
 * @param address Target flash address
 * @param start Sector start boundary
 * @param end Sector end boundary
 * @return true on success, false on failure
 */
TESTLIB_DLL_EXPORT bool firmware_download2flash(void* firmware, const char* data, uint32_t dataSize,
                                      uint32_t address, uint32_t start, uint32_t end);

/**
 * @brief Sends raw command to firmware
 * @param firmware Valid firmware handle
 * @param commandStr Command string to send
 * @param confirm Requires confirmation response when true
 * @param interval Command interval in milliseconds
 * @param times Number of command repetitions
 * @return true on success, false on failure
 */
TESTLIB_DLL_EXPORT bool firmware_send_command(void* device, const uint8_t* commandStr, bool confirm, uint32_t interval, uint32_t times);

/**
 * @brief Reads the firmware command reply payload (12 bytes) into @a commandStr
 * @param device Valid device handle
 * @param commandStr [out] Buffer with room for at least 12 bytes (FW_DATA_LENGTH); not null-terminated by default
 * @return true on success, false on failure
 */
TESTLIB_DLL_EXPORT bool firmware_read_command(void* device, char* commandStr);

/* -------------------------------------------------------------------------- */
/* Firmware automation exports (additive); semantics of symbols above are     */
/* unchanged.                                                                  */
/* -------------------------------------------------------------------------- */

/**
 * @brief Copies the thread-local last error message into a caller buffer
 * @param buf [out] Destination buffer for UTF-8 text (including null terminator)
 * @param buf_cap Capacity of @a buf in bytes
 * @note Primarily populated by the additive APIs below; empty if no error was set
 */
TESTLIB_DLL_EXPORT void testlib_get_last_error(char* buf, uint32_t buf_cap);

/**
 * @brief Clears the thread-local last error string
 */
TESTLIB_DLL_EXPORT void testlib_clear_last_error(void);

/**
 * @brief Performs I2C read into a raw byte buffer (register address width @a regSize)
 * @param device Valid device handle
 * @param slaveID 7-bit I2C slave address
 * @param uReg Register address (low 16 bits used per device stack)
 * @param regSize Register address size in bytes (e.g. 1 or 2)
 * @param pdata [out] Buffer receiving @a datalength bytes
 * @param datalength Number of bytes to read
 * @return true on success, false on failure
 */
TESTLIB_DLL_EXPORT bool device_I2C_Read_Data(void* device, uint8_t slaveID,
    uint16_t uReg, uint8_t regSize, uint8_t* pdata, uint16_t datalength);

/**
 * @brief Performs I2C write from a raw byte buffer (register address width @a regSize)
 * @param device Valid device handle
 * @param slaveID 7-bit I2C slave address
 * @param uReg Register address
 * @param regSize Register address size in bytes (e.g. 1 or 2)
 * @param pdata Payload bytes to write
 * @param datalength Number of bytes to write from @a pdata
 * @return true on success, false on failure
 */
TESTLIB_DLL_EXPORT bool device_I2C_Write_Data(void* device, uint8_t slaveID,
    uint16_t uReg, uint8_t regSize, uint8_t* pdata, uint16_t datalength);

/**
 * @brief Reads reboot / watchdog reset counters from firmware flash log
 * @param device Valid device handle
 * @param out_reboot_count [out] Cumulative reboot count (may be NULL if unused)
 * @param out_watchdog_reset_count [out] Watchdog reset count (may be NULL if unused)
 * @return true on success, false on failure
 */
TESTLIB_DLL_EXPORT bool firmware_get_flash_log(void* device,
    uint32_t* out_reboot_count, uint32_t* out_watchdog_reset_count);

/**
 * @brief Detects firmware presence on the device
 * @param device Valid device handle
 * @param read_customer_id When true, also refresh customer id in device state where applicable
 * @return true if firmware responds as expected, false otherwise
 */
TESTLIB_DLL_EXPORT bool firmware_detect(void* device, bool read_customer_id);

#define TESTLIB_FW_INFO_FIRMWARE_VERSION 0u
#define TESTLIB_FW_INFO_ROM_VERSION      1u
#define TESTLIB_FW_INFO_SRAM_VERSION     2u
#define TESTLIB_FW_INFO_BUILD_TIME       3u
#define TESTLIB_FW_INFO_STATUS           4u
#define TESTLIB_FW_INFO_CUSTOMER_ID      5u
#define TESTLIB_FW_INFO_JENKINS_LINK     6u

/**
 * @brief Retrieves a firmware information string (version, build time, etc.)
 * @param device Valid device handle
 * @param info_id One of TESTLIB_FW_INFO_* constants
 * @param buf [out] UTF-8 output buffer (null-terminated on success)
 * @param buf_cap Capacity of @a buf in bytes
 * @return true on success, false on failure
 */
TESTLIB_DLL_EXPORT bool firmware_get_info_string(void* device, uint32_t info_id,
    char* buf, uint32_t buf_cap);

/**
 * @brief Like device_grab_one_frame_save, and returns the captured frame id
 * @param device Valid device handle (streaming must be active)
 * @param savePath Directory path for the output file (UTF-8)
 * @param fileName File name without path (UTF-8)
 * @param out_frame_id [out] Receives FrameInformation::uFrameID when successful
 * @return true on success, false on failure
 */
TESTLIB_DLL_EXPORT bool device_grab_one_frame_save_ex(void* device, const char* savePath,
    const char* fileName, uint64_t* out_frame_id);

#define TESTLIB_OTP_MODE_WORK 0u
#define TESTLIB_OTP_MODE_RST  1u

/**
 * @brief Reads OTP content without storing it in the device-side OTP cache
 * @param device Valid device handle
 * @param base_addr OTP base address
 * @param size_bytes Number of bytes to read
 * @param out_buf [out] Buffer for raw OTP bytes
 * @param out_buf_cap Capacity of @a out_buf in bytes (must be >= size requested)
 * @param out_actual_len [out] Actual number of bytes written to @a out_buf
 * @param otp_mode OTP access mode (e.g. TESTLIB_OTP_MODE_WORK, TESTLIB_OTP_MODE_RST)
 * @param otp_read_mode Device-specific read mode passed to the driver stack
 * @return true on success, false on failure
 */
TESTLIB_DLL_EXPORT bool device_otp_read_unstore(void* device, uint16_t base_addr,
    uint32_t size_bytes, uint8_t* out_buf, uint32_t out_buf_cap, uint32_t* out_actual_len,
    uint32_t otp_mode, uint32_t otp_read_mode);

/**
 * @brief Reads OTP and writes the raw bytes to a file
 * @param device Valid device handle
 * @param base_addr OTP base address
 * @param size_bytes Number of bytes to read
 * @param utf8_path Output file path (UTF-8)
 * @param otp_mode OTP access mode (e.g. TESTLIB_OTP_MODE_WORK)
 * @param otp_read_mode Device-specific read mode
 * @return true on success, false on failure
 */
TESTLIB_DLL_EXPORT bool device_otp_save_file(void* device, uint16_t base_addr,
    uint32_t size_bytes, const char* utf8_path, uint32_t otp_mode, uint32_t otp_read_mode);

/**
 * @brief Writes data to OTP (irreversible on hardware; use with care)
 * @param device Valid device handle
 * @param addr OTP word/byte address per device convention
 * @param data Bytes to program
 * @param data_len Length of @a data
 * @param otp_mode OTP access mode
 * @param otp_read_mode Device-specific mode parameter forwarded to the stack
 * @return true on success, false on failure
 */
TESTLIB_DLL_EXPORT bool device_otp_write(void* device, uint16_t addr,
    const uint8_t* data, uint32_t data_len, uint32_t otp_mode, uint32_t otp_read_mode);

/**
 * @brief Returns the current OTP function flags bitmask from the device
 * @param device Valid device handle
 */
TESTLIB_DLL_EXPORT uint32_t device_otp_get_function_flags(void* device);

/**
 * @brief Sets OTP function flags on the device (semantics depend on sensor firmware)
 * @param device Valid device handle
 * @param flags Bitmask to apply
 */
TESTLIB_DLL_EXPORT void device_otp_set_function_flags(void* device, uint32_t flags);

#ifdef __cplusplus
}
#endif

#endif // TESTDEVICEEXPORT_H
