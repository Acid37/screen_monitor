# Screen Monitor (屏幕状态视觉感知插件)

这是一个为 Neo-MoFox 框架定做的“数字陪伴”增强插件。它能让你的 AI 助理获得“视觉”，在后台默默观察你正在使用的电脑屏幕，并在你们聊天时提供完全自然的上下文意会。

## ✨ 核心特性

- **后台静默捕获**：使用高性能的 `mss` 库在后台截取主屏幕画面，不干扰正常工作。
- **Token 燃烧防护 (防挂机)**：内置了基于 `Pillow` 的像素级画面差异比对算法。当主人离开座位或画面静止时，插件会自动暂停请求大模型，极大节省多模态 API 费用。
- **后置弱注入**：参考 `notice_injector` 的实现，在 `default_chatter_user_prompt` 构建阶段把屏幕观察追加到 `values.extra`，避免走 `actor` reminder 主链，更利于保护高缓存命中场景。
- **自动状态老化**：支持状态保留时间（TTL），如果长按时间没有新动态，旧的“监视记忆”会自动过期失效。

## 📦 依赖安装

本插件依赖用于屏幕截取的 `mss` 和用于图像压缩与对比的 `Pillow`。
如果你的环境尚未包含，请在项目根目录运行：

```bash
uv add mss Pillow
```

## ⚙️ 配置说明

首次运行加载本插件后，会在 `config/plugins/screen_monitor/config.toml` 中生成配置。

当前支持：

- 使用 `model_task` 或 `models` 覆盖模型
- 截图保存开关
- 日志开关
- 调试日志开关
- 差异阈值调节
- 自定义视觉分析提示词

```toml
[monitor]
enabled = true
interval_minutes = 10
run_once_on_start = false
run_once_delay_minutes = 1
retention_hours = 2
save_screenshot = false
monitor_index = 1
image_max_width = 1024
image_max_height = 1024
jpeg_quality = 80
diff_threshold = 2.0
prompt = "请理解这张屏幕截图，并总结主人当前正在做什么、关注什么、所处的场景状态。重点关注：正在使用的程序或网页、可见文字主题、当前操作焦点、可能的意图或上下文。请输出一段适合注入到对话上下文中的简洁中文描述，偏向‘主人现在在做什么’而不是逐项念图。不要输出过多琐碎 UI 细节，不要机械罗列控件。如果画面中可能含有账号、密码、验证码、身份证号、手机号、家庭住址、付款码等敏感信息，不要转写具体内容，只需模糊化描述。"
log_enabled = true
log_debug_details = false

[model]
model_task = "vlm"
models = []
temperature = 0.3
max_tokens = 800

```

实际生成到 `config/plugins/screen_monitor/config.toml` 的文件会自动带上：

- 字段注释
- 值类型
- 默认值说明

和你仓库里其他插件配置风格一致。

### 模型选择

默认：

```toml
model_task = "vlm"
models = []
```

表示直接使用 `config/model.toml` 中的对应 task。

如果你要自主选模型：

```toml
model_task = "vlm"
models = ["你的模型名"]
```

这里的 `models` 必须对应 `config/model.toml` 中的 `models.name`。

### 日志开关

- `log_enabled = true`：输出 info 级运行日志
- `log_debug_details = true`：输出更细的执行细节

你想看到自动调度有没有跑，就保持：

```toml
log_enabled = true
```

插件启动和每轮执行都会打日志。

### 首次运行开关

- `run_once_on_start = false`：启动后不立即截图，但会打印“插件已存活、下次大约多久执行”
- `run_once_on_start = true`：启动完成后先等待 `run_once_delay_minutes` 分钟，再执行首次分析，然后继续周期调度

## 🚀 工作流程

1. **定时触发**：根据 `interval_minutes` 时间进行一次截图，并把图片压缩至 1024x1024 限制 Token 消耗。
2. **差异检测**：将当前截图与上一张截图生成 64x64 的灰度指纹进行差异对比，如果均值差异小于阈值，说明屏幕闲置，直接复用旧状态，终止流程。
3. **VLM 分析**：调用大模型读取并概括画面。
4. **状态持久与挂载**：保存 json 数据，并将诸如 `[系统视觉观测 14:35] 助理察觉到主人的近期桌面动态：主人正在看 YouTube 视频` 这样的句子挂载至 Bot 的提醒记忆槽中。

## 💡 交互体验展示

主人：*“这人好蠢啊”*
助理：*“确实，刚在 B 站那个搞笑视频里，他的操作太下饭了（笑）”* 

由于助理感知到了你的桌面画面，你可以直接发出感叹，它能自动“意会”你的上下文场景。
