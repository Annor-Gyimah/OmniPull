#!/usr/bin/env python3
import xml.etree.ElementTree as ET

# Minimal translation mapping English -> (Japanese, Korean, Chinese)
translations = {
    "URL:": ("URL:", "URL:", "URL:"),
    "Save to:": ("保存先:", "저장 위치:", "保存到:"),
    "Category:": ("カテゴリ:", "카테고리:", "类别:"),
    "File name:": ("ファイル名:", "파일 이름:", "文件名:"),
    "Queue:": ("キュー:", "큐:", "队列:"),
    "Resolution:": ("解像度:", "해상도:", "分辨率:"),
    "Retry": ("再試行", "재시도", "重试"),
    "Change Folder": ("フォルダを変更", "폴더 변경", "更改文件夹"),
    "Cancel": ("キャンセル", "취소", "取消"),
    "Start Download": ("ダウンロード開始", "다운로드 시작", "开始下载"),
    "Add Download": ("ダウンロードを追加", "다운로드 추가", "添加下载"),
    "No completed downloads": ("完了したダウンロードはありません", "완료된 다운로드가 없습니다", "没有完成的下载"),
    "Queue": ("キュー", "큐", "队列"),
    "has started automatically": ("自動的に開始されました", "자동으로 시작되었습니다", "已自动开始"),
    "Queue Scheduler": ("キュー スケジューラー", "큐 스케줄러", "队列计划程序"),
    '"Deno" is required to solve JavaScript challenges for YouTube.\nInstall from the official docs or add the deno executable to PATH.': (
        'YouTube の JavaScript チャレンジを解決するには "Deno" が必要です。\n公式ドキュメントからインストールするか、deno 実行ファイルを PATH に追加してください。',
        'YouTube의 JavaScript 문제를 해결하려면 "Deno"가 필요합니다.\n공식 문서를 참조하여 설치하거나 deno 실행 파일을 PATH에 추가하세요.',
        '需要 "Deno" 来解决 YouTube 的 JavaScript 挑战。\n请从官方文档安装或将 deno 可执行文件添加到 PATH。'
    ),
    "Aria2c Warning": ("Aria2c の警告", "Aria2c 경고", "Aria2c 警告"),
    "This method is experimental and may not download or merge properly.": (
        "この方法は実験的です。ダウンロードやマージが正しく行われない場合があります。",
        "이 방법은 실험적이며 제대로 다운로드되거나 병합되지 않을 수 있습니다.",
        "此方法是实验性的，可能无法正确下载或合并。"
    ),
    "Do you want to continue?": ("続行しますか？", "계속하시겠습니까?", "要继续吗？"),
    "{name} is missing": ("{name} が見つかりません", "{name}가 없습니다", "缺少 {name}"),
    '"{name}" is missing and needs to be downloaded:': (
        '"{name}" が見つからず、ダウンロードが必要です:',
        '"{name}"가 없으며 다운로드해야 합니다:',
        '"{name}" 丢失，需要下载：'
    ),
    '"{name}" is required for this action.\nPlease install {name} with your OS package manager or provide its path in the app settings.': (
        'この操作には "{name}" が必要です。\nOS のパッケージマネージャで {name} をインストールするか、アプリ設定でパスを指定してください。',
        '이 작업에는 "{name}"이 필요합니다.\nOS 패키지 관리자에서 {name}을 설치하거나 앱 설정에 경로를 제공하세요.',
        '此操作需要 "{name}"。\n请使用您的操作系统包管理器安装 {name}，或在应用设置中提供其路径。'
    ),
    "Recommended:": ("推奨:", "권장:", "推荐："),
    "Local folder:": ("ローカルフォルダ:", "로컬 폴더:", "本地文件夹:"),
    "Download": ("ダウンロード", "다운로드", "下载"),
    "Error": ("エラー", "오류", "错误"),
    "No download item selected": ("ダウンロード項目が選択されていません", "선택된 다운로드 항목이 없습니다", "未选择下载项"),
    "Can't delete items while downloading. Stop or cancel all downloads first!": (
        "ダウンロード中に項目を削除できません。まずすべてのダウンロードを停止またはキャンセルしてください！",
        "다운로드 중에는 항목을 삭제할 수 없습니다. 먼저 모든 다운로드를 중지하거나 취소하세요!",
        "下载时无法删除项目。请先停止或取消所有下载！"
    ),
    "Warning!!!": ("警告!!!", "경고!!!", "警告!!!"),
    "Are you sure you want to delete these items?": ("これらの項目を削除してもよろしいですか？", "이 항목들을 삭제하시겠습니까?", "确定要删除这些项目吗？"),
    "Delete files?": ("ファイルを削除しますか？", "파일을 삭제하시겠습니까?", "删除文件？"),
    "File:": ("ファイル:", "파일:", "文件："),
    "has been deleted.": ("が削除されました。", "삭제되었습니다.", "已被删除。"),
    "Delete all items and their progress temp files": (
        "すべての項目と進行状況の一時ファイルを削除します",
        "모든 항목과 진행 임시 파일을 삭제합니다",
        "删除所有项目及其进度临时文件"
    ),
    "Type the word 'delete' and hit OK to proceed.": (
        "'delete' と入力して OK を押してください。",
        "'delete'를 입력하고 확인을 눌러 진행하세요.",
        "输入 'delete' 并点击确定以继续。"
    ),
    "Stop All": ("すべて停止", "모두 중지", "全部停止"),
    "There are no active downloads to stop.": (
        "停止するアクティブなダウンロードはありません。",
        "중지할 활성 다운로드가 없습니다.",
        "没有要停止的活动下载。"
    ),
    "Stop All Downloads?": ("すべてのダウンロードを停止しますか？", "모든 다운로드를 중지하시겠습니까?", "要停止所有下载吗？"),
    "Some downloads are currently active (Downloading, Pending, Merging).": (
        "現在いくつかのダウンロードがアクティブです（ダウンロード中、保留中、マージ中）。",
        "일부 다운로드가 현재 활성 상태입니다(다운로드 중, 보류, 병합 중).",
        "某些下载当前处于活动状态（下载中、等待、合并中）。"
    ),
    "Do you want to stop all?": ("すべて停止しますか？", "모두 중지하시겠습니까?", "要全部停止吗？"),
    "Stopped": ("停止", "중지됨", "已停止"),
    "All active downloads have been cancelled.": (
        "すべてのアクティブなダウンロードがキャンセルされました。",
        "모든 활성 다운로드가 취소되었습니다.",
        "所有活动下载已被取消。"
    ),
    # ... add more items as needed
}


def translate_file(input_ts, output_ts, lang_idx, lang_code):
    tree = ET.parse(input_ts)
    root = tree.getroot()
    root.set('language', lang_code)

    for message in root.findall('.//message'):
        source = message.find('source')
        translation = message.find('translation')
        if source is None or translation is None:
            continue
        s = source.text or ''
        if s in translations:
            translation.text = translations[s][lang_idx]
            if 'type' in translation.attrib:
                del translation.attrib['type']
        else:
            # If not found, default to source text (leave English) but remove unfinished
            translation.text = s
            if 'type' in translation.attrib:
                del translation.attrib['type']

    tree.write(output_ts, encoding='utf-8', xml_declaration=True)
    print('Wrote', output_ts)


if __name__ == '__main__':
    import os
    base = os.path.dirname(__file__)
    input_ts = os.path.join(base, 'app_en.ts')
    translate_file(input_ts, os.path.join(base, 'app_ja.ts'), 0, 'ja_JP')
    translate_file(input_ts, os.path.join(base, 'app_ko.ts'), 1, 'ko_KR')
    translate_file(input_ts, os.path.join(base, 'app_zh.ts'), 2, 'zh_CN')
