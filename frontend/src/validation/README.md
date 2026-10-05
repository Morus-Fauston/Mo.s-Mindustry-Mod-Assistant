# 校验报告组件接入

入口 `ValidationReportPanel.tsx`，DTO 在 `types.ts`，纯显示决策在 `presentation.ts`。

```tsx
<ValidationReportPanel report={report} currentSessionId={sessionId}
  currentRevision={revision} busy={validating} error={validationError}
  onValidate={validateProject} onLocate={locateIssue} />
```

- `onValidate` 由宿主接入真实校验；组件只防重复点击和显示回调错误，不读取工程、不持有桥接或业务历史。
- `onLocate` 收到后端原始 `ValidationIssue`，**App 必须再次核对报告 sessionId/revision**。同会话过期只允许打开同一精确文件，不使用旧字段地址、数组下标或行列。跨会话定位在组件内已禁用。
- `target: unavailable` 或空路径不可定位；`mod.json` 显示为工程信息文件，后端须指定不可定位。`form/source/file` 定位反馈由 App 执行后显示，组件不会声称已经定位成功。
- 问题消息和计数完全取自后端。只有当前报告完整、零错误和零警告、无执行失败时显示“本次校验未发现问题”。这不代表游戏引擎验收通过。
- 状态、消息和路径保留中文说明与完整文件身份；不把同名文件合并，不把字段键自行翻译为显示名。
- 样式使用集中 CSS 变量及 CSS Modules，无额外色值、输入框或动效。错误/警告文字不依赖颜色区分。现有马卡龙输入样式保持不变。

本目录测试覆盖静态渲染、状态身份、无精确定位与同名路径，不代替 Windows WebView2 实宿主的点击、折叠展开和源码定位验收。App 完成接线后须验证快速切工程、过期数组问题、两分类同名文件和失败重试。
