# Scheduler 信号审计配置(NixOS auditd)

## 背景

2026-06-26:scheduler 在无人操作下收到 SIGINT 后 `exit 0`,systemd 当时配置 `Restart=on-failure` 不重启(exit 0 非 failure)→ 同步中断、fundflow 首次回填数据全部丢失。

2026-07-07 再次发生:北京 04:32:56 scheduler 收到 SIGTERM(signal handler 已记录),打断了 stock_basic 第 3 次重试后的 60min sleep,导致 mark_failed 未执行,sync_state 卡 running。**sender 仍未定位**(signal handler 只能记信号 + 时刻,拿不到发送者 PID)。

已做的两层防御:
1. **`Restart=always`**(已生效):任何退出都自动重启,无论根因都能自愈。
2. **Python signal handler**(已生效,2026-07-07 已验证):`_register_signal_audit` 记录收到 SIGINT/SIGTERM 的信号名 + 精确时刻 + 当时状态。04:32 SIGTERM + 15:26/15:48 SIGTERM 均有 WARNING 记录,确认 handler 工作正常。下次再被杀,日志里至少有「确实是信号 + 哪种信号」的证据。

**但纯用户态拿不到信号发送者 PID**(POSIX 信号机制不向接收进程传递 sender)。要抓 sender,必须用内核级 auditd。本文档是这部分配置,需 **sudo 执行**。

### 2026-07-07 排查补充

排查 04:32 SIGTERM 时,穷尽了否定证据(无 OOM/无 systemd stop 记录/无代码异常/无 nixos rebuild),同期 ollama/podman 日志全是周期性健康检查(非杀进程动作)。**结论:进程收到 SIGTERM,但发送者无法从现有日志定位**——这正是本配置要解决的。

**重要区分**:排查中还发现 scheduler 反复重启但**无 signal 记录**的情况(15:08-15:21,5 次/30s 间隔)。这不是信号杀进程,而是**进程崩溃**(AM session 冲突——同时跑独立 AM 诊断脚本会挤掉 scheduler 的 SDK 单例 session,参见 AGENTS.md 2026-07-04「真根因 1」)。崩溃走 systemd Restart 自愈,与信号溯源是两类问题。本配置只针对「signal handler 记录了 SIGTERM 但 sender 未知」的场景。

---

## 配置(NixOS)

> **2026-08-25 更新:以下配置已模块化到 nixos-config 仓库 `modules/system/auditd.nix`**(2026-07-07 准备),应用方式改为在 nixos-config 目录 `sudo nixos-rebuild switch --flake .#lenovo`。下文 configuration.nix 手工步骤仅作配置内容参考,**仍待用户 sudo 应用**(.work/TODO.md 长期遗留)。

在 `/etc/nixos/configuration.nix` 的 `configuration` 函数体内添加(= auditd.nix 模块内容):

```nix
  # 内核审计:scheduler 信号溯源(2026-06-26)
  # scheduler 曾在无人操作下收到 SIGINT 后 exit 0 无记录,无法定位发送者。
  # 此配置审计 kill 系统调用,捕获谁给谁发了什么信号。
  security.audit.enable = true;
  security.auditd.enable = true;
  security.audit.rules = [
    # 审计所有 kill/tkill/tgkill 系统调用,记录发送者(a0=目标PID, a1=信号)
    # -k galaxy-signal 给规则打 key,事后用 ausearch -k galaxy-signal 过滤
    # 注意:这会记录系统上所有 kill 调用(含 systemd/容器),日志量较大。
    # 如噪音过多,可改用 -F a1=15(只审 SIGTERM)或 -F a1=2(只审 SIGINT)收窄。
    "-a exit,always -F arch=b64 -S kill -S tkill -S tgkill -k galaxy-signal"
    "-a exit,always -F arch=b32 -S kill -S tkill -S tgkill -k galaxy-signal"
  ];
```

### 应用配置

```bash
# 1. 编辑配置(需 sudo)
sudo nano /etc/nixos/configuration.nix
#    把上面的 security.audit.* 段贴入 configuration 函数体内

# 2. 先用 build-vm 验证(audit 配置改动后会锁定,重建前务必测试)
#    参考:NixOS audit 模块文档提示"changing configuration prevents changing
#    audit config until restart — test with build-vm beforehand"
sudo nixos-rebuild build-vm  # 可选但推荐

# 3. 应用配置(需 sudo + 可能重启)
sudo nixos-rebuild switch
#    若 audit 配置无法热加载,需重启:sudo reboot
```

---

## 验证

```bash
# 1. 确认 auditd 运行
sudo systemctl status auditd

# 2. 确认规则加载
sudo auditctl -l
#    应显示:
#    -a always,exit -F arch=b64 -S kill -S tkill -S tgkill -k galaxy-signal
#    -a always,exit -F arch=b32 -S kill -S tkill -S tgkill -k galaxy-signal

# 3. 测试:发个信号给自己,看是否被记录
kill -TERM $$  # 当前 shell 给自己发 SIGTERM(会退出 shell,用新终端查)
sudo ausearch -k galaxy-signal -ts recent | tail -20

# 4. 事后查 scheduler 相关信号事件
#    scheduler 被杀后,用此命令查发送者(a0=目标PID, exe=发送者进程)
sudo ausearch -k galaxy-signal --interpret | grep -A5 "galaxy_core\|scheduler"
```

### ausearch 输出解读

一次 kill 事件的典型输出:
```
----
type=SYSCALL msg=audit(2026-06-27 01:13:27.350): arch=c000003e syscall=62 \
  success=yes exit=0 a0=21214 a1=f a2=0 a3=7f... \
  ... pid=18354 ... exe=/nix/store/.../systemd ... \
  ... key="galaxy-signal"
```
- `a0=21214`:目标 PID(scheduler)
- `a1=f`:信号编号(f = 15 = SIGTERM)
- `pid=18354 ... exe=...`:**发送者 PID 和可执行文件** ← 这就是我们要抓的
- `key="galaxy-signal"`:规则标记,方便过滤

---

## 注意事项

1. **日志量**:`-S kill` 会记录系统上**所有** kill 调用(systemd 停服务、容器健康检查、pkill 等都会触发)。日常可能每分钟数条。如果噪音过大,改用收窄规则:
   ```nix
   security.audit.rules = [
     # 只审 SIGTERM(15)和 SIGINT(2),减少噪音
     "-a exit,always -F arch=b64 -S kill -F a1=15 -k galaxy-signal"
     "-a exit,always -F arch=b64 -S kill -F a1=2 -k galaxy-signal"
   ];
   ```
2. **审计锁定**:NixOS audit 模块文档提示,改 audit 配置后可能锁定到重启。**务必先 `nixos-rebuild build-vm` 测试**,避免配置错误导致审计无法调整。
3. **性能**:audit 规则有轻微性能开销(每次 kill 多一次内核记录)。对单机桌面/服务器影响可忽略。
4. **回滚**:如不再需要,删除 `security.audit.*` 段后 `sudo nixos-rebuild switch` 即可关闭。

---

## 与 Python signal handler 的关系

| 层 | 能力 | 已实现? |
|---|---|---|
| Python `_register_signal_audit` | 记录「收到信号 + 时刻 + 当时状态」 | ✅ 已生效 |
| NixOS auditd(本文档) | 记录「**谁**发的信号 + 发送者进程」 | ⬜ 需 sudo 配置 |

两者互补:Python 层提供即时、轻量的证据(重启即生效);auditd 层提供完整溯源(需系统配置)。auditd 配好后,下次 scheduler 再被杀,`ausearch -k galaxy-signal` 就能定位发送者进程。
