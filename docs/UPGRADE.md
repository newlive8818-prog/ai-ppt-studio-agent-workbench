# 升级说明

刷新已配置的 Git Marketplace：

```bash
codex plugin marketplace upgrade newlive8818-ai-ppt-studio
```

然后重新安装当前 Marketplace 中的插件版本：

```bash
codex plugin add ai-ppt-studio@newlive8818-ai-ppt-studio
```

检查登记：

```bash
codex plugin list --json
```

升级后请新建 Codex 对话；若宿主仍显示旧工具目录，再重启 Codex。不要手工覆盖插件 cache，也不要把版本字符串本身当作已加载证明。实际加载应核对插件 ID、版本和公开工具数。
