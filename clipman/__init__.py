"""剪贴板历史管理器(Linux · PyQt6)

功能:
  · 自动记录复制的文本、图片、表情包、文件,常驻后历史内容随时可再次粘贴
  · 单击条目 → 放回剪贴板并自动粘贴到上一个窗口(需要 xdotool)
  · 支持把条目直接拖拽到目标应用完成粘贴;也支持从外部拖内容进来收藏
  · 列表内拖动条目可调整位置
  · 白色背景,文本默认黑体黑字,右键可为指定条目修改字体颜色
  · 历史自动持久化到 ~/.local/share/clipboard-manager/

模块划分:
  constants        路径、默认配置、界面常量与黑体字体
  hotkey           快捷键格式转换(Qt/X11/GNOME)与 XGrabKey 全局快捷键
  gnome            GNOME 系统快捷键的查询、冲突检测与自定义绑定
  clip_item        单条剪贴历史的数据模型与序列化
  settings_dialog  设置对话框
  preview_popup    悬浮预览/编辑弹窗
  cards            卡片控件与带动画的卡片列表容器
  main_window      主窗口(剪贴板监听、条目管理、持久化)
  selftest         无显示环境也能跑的自测
  app              程序入口(单实例、toggle.sh 生成)
"""
