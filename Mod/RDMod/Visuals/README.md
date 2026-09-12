# 超速费用特效

在 Godot 中导入 `Mod/project.godot`。

- 编辑特效：`res://RDMod/Visuals/OverdriveCostGlow.tscn`。
- 运行预览：打开 `res://RDMod/Visuals/OverdriveCostGlowPreview.tscn`，按 F6。
- 预览操作：空格切换显示，+/- 缩放，O 切换三张示例卡的重叠。

选择特效根节点，在 Inspector 修改 Modulate（整体乘色，彩虹模式保持白色）、Glow Margin（外围空间）、Transition Duration（过渡秒数）。展开 Material → Shader Parameters 调整 radius_expansion（半径扩展）、width（宽度）、ripple_speed（速度）、modulo_width（波纹间隔）和 ease（波纹边缘过渡）。activation、icon_size、canvas_size 由显示控制与图标布局更新。

彩虹颜色沿圆周分布，每道波纹都包含完整彩虹；向外扩散继续使用原有波纹公式。默认颜色位置固定，可在 Material → Shader Parameters 调节：

| 参数 | 用途 | 默认值 |
| --- | --- | --- |
| rainbow_saturation | 饱和度，0 为白色，1 为纯彩色 | 0.85 |
| rainbow_brightness | 彩虹亮度 | 0.85 |
| rainbow_offset | 颜色起点，0–1 对应一圈 | 0 |
| rainbow_rotation_speed | 每秒旋转圈数；0 固定，负值反向 | 0 |

例如将 rainbow_rotation_speed 改为 0.02，即每 50 秒旋转一圈。彩虹由 Shader 按圆周角度采样 GradientTexture1D，纹理由 Godot 的 Gradient 自动生成，无需绘制 PNG。

预览引用游戏使用的同一份特效场景。编辑特效本体，避免仅修改预览实例的覆盖值。预览卡面是用于检查遮挡的示意卡面。

游戏内仍挂在 NCard.Body 下、EnergyIcon 之前，保持 z_index=0、相对 Z、鼠标忽略及父级变换。编辑时共享外部 ShaderMaterial；运行时在 _ready 中复制材质，显示动画互不影响。Shader 与纹理可共享。C# 仅判断显示条件、加载缓存场景和同步布局。

修改资源后运行 `python Scripts/debug_after_code.py --export-pck`，将更新导出至游戏并重启加载。

验证记录（2026-09-12）：Godot 4.5.1 导入无错误；实际渲染预览检查光圈位于图标和数字之后；独立材质、相对 Z、鼠标忽略、单实例开关和过渡断言通过。项目自动调试完成构建、12 个本地化 JSON 与 94 张卡关键词静态检查、PCK 导出及游戏初始化（AUTO_DEBUG_OK）。本次没有改变超速资格或支付规则。预览验证不替代真实手牌所有拖拽状态的视觉检查。

彩虹更新验证（2026-09-12）：使用项目 Forward Mobile / Vulkan 渲染器实际渲染；Shader 无错误，完整圆周渐变和费用数字遮挡正常，材质隔离与淡入淡出断言通过。

## 编辑彩虹颜色分布

打开 `res://RDMod/Visuals/OverdriveRainbowGradient.tres`，展开 Gradient，拖动色标位置控制各段过渡长度，也可增加、删除色标或修改颜色及透明度。它是游戏和预览共享的 GradientTexture1D 资源，采样宽度为 1024。

也可从特效根节点 Material → Shader Parameters → Rainbow Gradient → Gradient 进入。渐变 0–1 对应完整一圈，色标间距 0.1 对应 36°；拉开两个色标会延长两色之间的渐变。若要扩大某个颜色的纯色区域，可添加两个相同颜色的色标。

保持位置 0 和 1 的色标颜色及透明度相同，使圆环首尾连续。默认首尾均为红色。颜色旋转只改变采样起点，不改动色标分布。运行时动画仅修改每张牌独立材质的 activation，不修改共享渐变资源。

GradientTexture1D 更新验证（2026-09-12）：Forward Mobile 实际渲染、场景绑定、默认首尾同色、移动色标后纹理重新生成断言通过；PCK 导出、构建与游戏加载 AUTO_DEBUG_OK。无界面渲染器无法读取纹理图像，纹理更新检查使用实际渲染器完成。

预览覆盖同步验证（2026-09-12）：将预览第一张卡独立材质中的外观参数应用到特效本体，移除预览材质覆盖。隔离项目直接加载游戏安装目录的 RDmod.pck，验证三张卡 radius_expansion=0、width=0.07、rainbow_brightness=1、ripple_speed=0.04、Size=128×128；材质隔离、层级及过渡检查通过，游戏 AUTO_DEBUG_OK。

## 共用材质资源

材质保存为 `res://RDMod/Visuals/OverdriveCostGlowMaterial.tres`。特效本体通过外部引用使用它，预览通过引用特效本体使用同一材质来源。

可以直接打开材质文件，也可以在 OverdriveCostGlow.tscn 根节点的 Material 中展开 Shader Parameters 修改。编辑的是同一份外部材质；保存全部资源后再导出 PCK。保持外部引用，不使用 Make Unique、另存为新材质或拖入另一份材质，这些操作会建立单独版本。

编辑时材质共享；实际运行时脚本复制材质，仅让该牌的尺寸与显隐动画独立。运行中的调试实例不会自动写回素材文件。修改源材质后重新运行预览或重新导出并重启游戏。
共享材质验证（2026-09-12）：断言场景实例入树前引用外部材质，修改材质源参数后新实例继承该值；入树后独立复制，显隐变化不影响材质源。三张预览卡材质隔离、层级与动画检查通过；构建、PCK 导出、游戏初始化 AUTO_DEBUG_OK。
