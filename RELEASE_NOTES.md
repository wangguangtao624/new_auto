# New Auto 2.2.0

## Highlights

- 画布编辑器采用工业控制台视觉，支持节点搜索、运行监控和数据连线。
- AI 用例生成入口、模型状态与本地 Key 状态可见。
- COM3 / Channel 0 改为 PixelIDE SDK 真实继电器控制，不再使用无回执的 A0 串口假成功判断。
- 新增 `case333` 真机演示：出图、FPS 数据断言、I2C 固件版本数据断言。

## Verified hardware result

- Channel 0：SDK 断电 15 秒后重新上电成功。
- 真机出图：成功，FPS 25.01，DN 71.71。
- 固件主版本断言：4，通过。
