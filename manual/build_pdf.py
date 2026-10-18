"""Build Based-Quake-Installer-Manual.pdf from the Markdown source (WeasyPrint)."""
import os, re, markdown, weasyprint, html
os.chdir(os.path.dirname(os.path.abspath(__file__)))
SRC = "Based-Quake-Installer-Manual.md"
md = open(SRC, encoding="utf-8").read()
body = markdown.markdown(md, extensions=["tables", "fenced_code", "toc", "md_in_html", "sane_lists"],
                         extension_configs={"toc": {"permalink": False}})
# images-only paragraphs -> figures with captions
body = re.sub(r'<p><img alt="([^"]*)" src="([^"]*)" ?/?></p>',
              lambda m: '<figure><img src="%s" alt="%s"><figcaption>%s</figcaption></figure>'
              % (m.group(2), m.group(1), html.escape(html.unescape(m.group(1)))), body)
# chapter h1s get a class for page breaks (skip title/toc headings)
toc = []
for lvl, hid, txt in re.findall(r'<h([12]) id="([^"]+)">(.*?)</h\1>', body):
    toc.append('<li class="toc%s"><a href="#%s">%s</a></li>' % (lvl, hid, txt))
body = body.replace("<!--TOC-->", '<ul class="toc">%s</ul>' % "".join(toc))
body = re.sub(r'<h1 id=', '<h1 class="chapter" id=', body)
css = open("manual.css", encoding="utf-8").read()
doc = '<!doctype html><html><head><meta charset="utf-8"><title>Based Quake Installer v1.6.3 – User Manual</title><meta name="author" content="USDQC"><meta name="description" content="User manual for Based Quake Installer 1.6.3"><meta name="generator" content="Based Quake Installer manual build"><style>%s</style></head><body>%s</body></html>' % (css, body)
open("Based-Quake-Installer-Manual.html", "w", encoding="utf-8").write(doc)
weasyprint.HTML(string=doc, base_url=".").write_pdf("Based-Quake-Installer-Manual.pdf")
print("ok")
