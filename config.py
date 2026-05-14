"""screen_monitor 插件配置。"""

from __future__ import annotations

from typing import ClassVar

from src.core.components.base.config import BaseConfig, Field, SectionBase, config_section


class ScreenMonitorConfig(BaseConfig):
    """屏幕监控（主动视觉感知）插件配置。"""

    config_name: ClassVar[str] = "config"
    config_description: ClassVar[str] = "屏幕监控（主动视觉感知）插件的配置"

    @config_section("monitor")
    class MonitorSection(SectionBase):
        """监控主配置。"""

        enabled: bool = Field(default=True, description="是否开启屏幕监控")
        interval_minutes: int = Field(default=10, description="屏幕监控周期（分钟）")
        run_once_on_start: bool = Field(default=False, description="是否在启动完成后立即执行一次屏幕分析")
        run_once_delay_minutes: int = Field(default=1, description="启动后首次分析延迟分钟数，仅在 run_once_on_start=true 时生效")
        retention_hours: int = Field(default=2, description="状态过期时间（小时）。较早前拿到的状态会自动失效")
        save_screenshot: bool = Field(default=False, description="是否将截图保存到 data/screenshots 目录")
        monitor_index: int = Field(default=1, description="截取的显示器索引，1=主显示器")
        image_max_width: int = Field(default=1024, description="发送给 VLM 前的图片最大宽度")
        image_max_height: int = Field(default=1024, description="发送给 VLM 前的图片最大高度")
        jpeg_quality: int = Field(default=80, description="JPEG 压缩质量，范围建议 1-100")
        diff_threshold: float = Field(default=2.0, description="画面变化阈值；越小越敏感，越大越容易跳过分析")
        prompt: str = Field(
            default=(
                "请理解这张屏幕截图，并总结用户当前正在做什么、关注什么、所处的场景状态。"
                "重点关注：正在使用的程序或网页、可见文字主题、当前操作焦点、可能的意图或上下文。"
                "请输出一段适合注入到对话上下文中的简洁中文描述，偏向‘用户现在在做什么’而不是逐项念图。"
                "不要输出过多琐碎 UI 细节，不要机械罗列控件。"
                "如果画面中可能含有账号、密码、验证码、身份证号、手机号、家庭住址、付款码等敏感信息，不要转写具体内容，只需模糊化描述。"
            ),
            description="给视觉模型的分析提示词",
        )
        log_enabled: bool = Field(default=True, description="是否输出插件运行日志")

    @config_section("model")
    class ModelSection(SectionBase):
        """模型选择配置。"""

        model_task: str = Field(default="vlm", description="LLM 模型任务名（对应 model.toml 中的 task），models 为空时使用")
        models: list[str] = Field(default_factory=list, description="指定 LLM 模型列表（对应 model.toml 中的 name）。非空时覆盖 model_task，多个模型按顺序 fallback")
        temperature: float = Field(default=0.3, description="模型温度，仅在 models 非空时生效")
        max_tokens: int = Field(default=800, description="最大输出 token 数，仅在 models 非空时生效")

    @config_section("inject")
    class InjectSection(SectionBase):
        """注入配置。"""

        prompt_template: str = Field(
            default=(
                "这是对用户屏幕的实时观测，可帮助你感知用户当前在做什么，仅作参考：\n{observation}"
            ),
            description="注入到 LLM 上下文的模板，{observation} 会被替换为观测文本",
        )

    monitor: MonitorSection = Field(default_factory=MonitorSection)
    model: ModelSection = Field(default_factory=ModelSection)
    inject: InjectSection = Field(default_factory=InjectSection)
