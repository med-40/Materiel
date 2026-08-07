"""
core/templating.py
--------------------
كل وحدة تملك مجلد templates خاص بها (app/modules/<name>/templates)، لكن
القالب الأساسي المشترك (base.html - فيه القائمة العلوية والتخطيط العام)
موجود بمكان واحد فقط: web/templates/.

get_module_templates() تجمع المسارين حتى يشتغل {% extends "base.html" %}
داخل أي قالب خاص بأي وحدة، دون ما تحتاج كل وحدة تكرر نسخة من base.html.
"""

from fastapi.templating import Jinja2Templates

SHARED_TEMPLATES_DIR = "web/templates"


def get_module_templates(module_templates_dir: str) -> Jinja2Templates:
    return Jinja2Templates(directory=[module_templates_dir, SHARED_TEMPLATES_DIR])
