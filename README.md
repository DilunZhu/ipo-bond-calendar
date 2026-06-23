# 打新日历

自动生成新股 + 可转债打新日历 ICS 文件，支持 Apple Calendar / Google Calendar / Outlook 等日历应用订阅。

## 📲 订阅方式

创建仓库并开启 GitHub Pages 后，使用以下 URL 订阅：

```
https://<你的用户名>.github.io/<仓库名>/ipo_bond_calendar.ics
```

### Apple Calendar (iPhone/Mac)
1. 打开「日历」App
2. 底部「日历」→「添加日历」→「添加订阅日历」
3. 粘贴上面的 URL → 完成

### Google Calendar
1. 左侧「其他日历」→「从 URL」
2. 粘贴 URL → 添加日历

### Outlook
1. 「添加日历」→「从网页订阅」
2. 粘贴 URL

## 🚀 部署步骤

1. **Fork 或创建仓库**
   ```bash
   git clone https://github.com/<你的用户名>/ipo-bond-calendar.git
   cd ipo-bond-calendar
   ```

2. **首次运行生成 ICS**
   ```bash
   pip install requests
   python generate_ics.py
   git add .
   git commit -m "初始化打新日历"
   git push
   ```

3. **开启 GitHub Pages**
   - 仓库 Settings → Pages
   - Source 选择 `Deploy from a branch`
   - Branch 选 `main`，目录选 `/docs`
   - 保存

4. **验证**
   - 访问 `https://<用户名>.github.io/<仓库名>/ipo_bond_calendar.ics`
   - 确认可以下载 ICS 文件

5. **订阅**
   - 将上面的 URL 添加到日历 App

## ⏰ 自动更新

GitHub Actions 每天 09:00 自动执行：
- 从东方财富获取最新新股/新债数据
- 生成 ICS 文件并提交到 `docs/` 目录
- 日历 App 会按 `REFRESH-INTERVAL` 定期拉取更新

也可手动触发：Actions → Update IPO/Bond Calendar → Run workflow

## 📋 日历内容

| 类型 | 日程标题 | 日程详情 |
|------|---------|--------------|
| 新债 | 新债丨XX转债 | XXXXXX丨9:15-15:00 |
| 新股 | 新股丨XX股份 | XX交易所丨XXXXXX丨9:15-11:30/13:00-15:00 |

详情依次为：市场/代码/申购时间，简洁清晰。

每个事件前一天 15:00 会有提醒通知。

## ⚠️ 注意

- 数据来自东方财富公开 API，仅供参考
- 新股/新债发行时间可能临时调整，请以交易所公告为准
- GitHub Actions 的 cron 不保证精确到分钟执行，可能有几分钟延迟

## 🙏 鸣谢

 [bond-calendar-notify](https://github.com/YUTING0907/bond-calendar-notify)，一个通过 GitHub Actions + Server 酱实现新债打新微信定时提醒的开源项目。本项目在其思路上延伸，增加了新股数据和 ICS 日历订阅功能，让打新提醒直接集成到日常使用的日历 App 中。
