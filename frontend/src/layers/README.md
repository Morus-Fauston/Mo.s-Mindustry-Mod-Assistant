# 第 14 票图层树接入

本目录只拥有图层视图。`LayerTree` 的所有业务回调都由 App 提供；不访问 bridge，不持有文档副本或历史。样式沿左侧工程树，CSS Modules 与集中令牌；树标题行 24px、缩进 18px。武器坐标在标题行下用一行双列显示，输入本身复用 BasicForm 导出的 FieldControl，保留其 30px 高度、10px padding 与 1px border；预期文本起点为 11px，窄栏时标签移到输入上方。实际 WebView2 测量由主代理整合后执行。

## 导出

- `LayerTree.tsx`：`LayerTree`、`LayerTreeProps`；再导出 `LayerNode`、`LayerViewState`、`WeaponAnchor`、`reconcileLayerView`、`revealLayerView`。
- `types.ts`：后端实际 LayerNode DTO。`node.weapon.coordinates.x/y` 是原有 FormField，权限来自 Python。
- `view.ts`：纯视图 helpers，包含展开扁平化、祖先查询、状态清理、显式定位、树键盘行为；没有数值解析或数据写入。

## 调用约定

1. root 按 `[sessionId,path]` 保存 `{ selectedId, hiddenIds, closedIds }`，传当前路径已提交的场景树。只有收到同 session/path 且有效 revision 的完整场景后，才调用 `reconcileLayerView(nodes,state)` 清理无效节点；不要用加载期间的临时空数组清掉用户状态。关闭文档和切工程清理对应状态。
2. `onSelect(id)` 只选中；`onVisibility(id, visible)` 只维护 hiddenIds；`onExpanded(id, expanded)` 只维护 closedIds。它们不需要业务 RPC，组件也不会因为选择而改变显隐。`disabled` 仅禁用坐标业务输入和参数定位，显隐、折叠及选择仍可作为纯视图操作。
3. `selectedId` 改变时组件会请求展开必要祖先并滚动到该行，不转移焦点。对同一 selectedId 再次显式“定位图层”，root 应调用 `revealLayerView(nodes,state,id)`，这样已选项被用户折叠后也能重新展开。root 如果还要求重复滚动，可在其明确定位事件中定位 `[data-layer-id]`；不要通过随机 key 重挂整个树。
4. `onRevealParameters({sessionId,path,itemId,objectPath})` 由 root 验证当前表单身份后展开中央祖先并聚焦。组件不会用名字或 index 定位。引用、镜像和同名武器都使用后端 nodeId/itemId。
5. `drafts/errors` 是当前文档完整的 encoded key 映射。组件用 `encodeFieldKey(weapon.objectPath,'x'|'y')` 给 `onDraft(key,text)`、`onCommit(key): Promise<void>`、`onReset(key)`、`onComposition(key,active)`，直接接共享 draftStore。不得再创建图层独立草稿或业务保存入口。
6. FieldControl 保留 Enter/失焦提交、Esc 重置、IME 阻止提交、只读与 aria-invalid。图层页只显示坐标输入，不显示删除/置空菜单；不做前端 float 解析或 clamp。
7. 树焦点在 treeitem 上时：上下/Home/End 移焦；左右折叠/展开或进入父子；Space 显隐；Enter 选择。坐标、复选框或按钮获得焦点时由对应原生控件处理按键，不劫持输入方向键。

## 接入验证边界

本目录静态渲染测试只证明 DTO、共享草稿/错误、只读/禁用、折叠结构；纯 helper 测试证明稳定身份清理及键盘决策。它们不能替代真实宿主点击热区、焦点、全部输入起点、DPI 和桥接保存/撤销验收。
