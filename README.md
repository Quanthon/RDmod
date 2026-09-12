# Rainbow Dash / 云宝黛西

《杀戮尖塔 2》角色 Mod，围绕蓄力、飞行和超速机制，支持简体中文和英文。
A Slay the Spire 2 character mod featuring Charge, Flight and Overdrive, with Chinese and English localization.

## 下载与安装 / Download and install

在 [Releases](https://github.com/Quanthon/RDmod/releases) 下载 `RainbowDash-版本号.zip`。
ZIP 内含完整的 RDmod.dll、RDmod.pck、RDmod.json，解压到游戏目录 `mods/RDmod/`。
需单独安装 [RitsuLib](https://steamcommunity.com/sharedfiles/filedetails/?id=3747602295)。
GitHub 的 Source code ZIP 是源码；直接游玩请下载 RainbowDash 发布包。

Download `RainbowDash-<version>.zip` from Releases and extract its three files into
`mods/RDmod/` under the game directory. Install RitsuLib separately.
Use the RainbowDash release ZIP for gameplay, or the source archive for development.

## 从源码构建 / Building

需要 .NET 9 SDK、Godot 4.5.1 .NET 版，以及已安装的游戏。
在仓库目录运行下列命令，将路径替换为自己的安装位置：

```powershell
dotnet build Mod/RDmod.csproj -c Release -p:SkipModInstall=true "-p:Sts2Dir=D:/your/Slay the Spire 2"
dotnet msbuild Mod/RDmod.csproj -t:ExportPck -p:Configuration=Release "-p:GodotExe=D:/your/Godot.exe" "-p:Sts2Dir=D:/your/Slay the Spire 2" "-p:PckOutputPath=D:/your/output/RDmod.pck"
```

DLL 位于 `Mod/.godot/mono/temp/bin/Release/RDmod.dll`，与生成的 PCK 和 `Mod/RDmod.json` 一起安装。
图片、场景、本地化和音频源文件包含在 `Mod/`，构建无需私人设计工作簿或官方反编译参考目录。
包依赖使用 NuGet 恢复，游戏程序集从自己的游戏安装目录引用。

## 许可证 / License

代码：MIT，见 [LICENSE](LICENSE)。图片和音频等见 [ASSET_NOTICE.md](ASSET_NOTICE.md)。
当前测试环境和已知兼容边界见 [1.0.0 发布说明](docs/1.0.0发布说明.md)。

## 发布工具 / Publication tools

一键GitHub与工坊发布流程见 [上传工作流](docs/创意工坊上传工作流.md)。
使用这些可选工具需要 Python 与 Pillow（`python -m pip install Pillow`），以及按文档安装的 GitHub CLI 和官方 ModUploader；编译 Mod 本身不依赖这些发布工具。
