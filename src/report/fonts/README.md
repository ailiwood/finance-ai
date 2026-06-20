# CJK Font for PDF Export

Place a CJK TrueType font file here named `cjk_font.ttf`.

## Windows
Copy from system fonts:
```
copy C:\Windows\Fonts\simhei.ttf cjk_font.ttf
```

## Linux / Docker
Install Noto CJK:
```
apt-get install fonts-noto-cjk
cp /usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc cjk_font.ttf
```
Note: fpdf2 may not handle .ttc files well. Use `fonttools` to extract:
```
pip install fonttools
python -c "from fontTools.ttLib import TTCollection; c=TTCollection('NotoSansCJK-Regular.ttc'); c[0].save('cjk_font.ttf')"
```

## macOS
```
cp /System/Library/Fonts/PingFang.ttc cjk_font.ttf
```

## License
Please ensure you have the right to redistribute the font you choose.
Open-source options: Noto Sans SC (SIL OFL), WenQuanYi (GPL).
