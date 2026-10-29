# 发布到 GitHub

## 建仓库

1. 登录 GitHub，选择 **New repository**。
2. 仓库名可用 `crackscope-stereo-crack-measurement`，简介写“基于双目深度相机的裂缝分割与宽度测量”。
3. 选择 **Public**，因为本项目希望公开源码。
4. 不要勾选初始化 README、`.gitignore` 或 License；这些文件已在本地仓库准备好。

## 推送本地仓库

在此项目根目录 `D:\LEON\MyCode\crack_scope` 打开 PowerShell。将 `<你的 GitHub 用户名>` 换成自己的账号：

```powershell
git status
git remote add origin https://github.com/<你的 GitHub 用户名>/crackscope-stereo-crack-measurement.git
git push -u origin main
```

首次推送需要按 Git Credential Manager 提示登录。推送后打开 GitHub 仓库首页，确认 README、教程、源码和 `LICENSE` 均显示正常。

## 推送前检查

```powershell
git status --short
git check-ignore -v models/best.pt
git ls-files | Select-String -Pattern '\.pt$|\.onnx$|\.db$|\.env$|\.img(\.xz)?$|\.docx$'
```

最后一条命令应无输出。`.env.example` 是不含凭据的配置模板，允许提交；真实 `.env`、模型权重、数据库、系统镜像和课程报告都不应进入仓库。

公开前还要确认 [第三方素材记录](../THIRD_PARTY_NOTICES.md) 中的图片来源和再发布许可。MIT 只涵盖项目原创代码与文档，不替代图片、模型数据集、Chart.js 等第三方材料各自的许可。
