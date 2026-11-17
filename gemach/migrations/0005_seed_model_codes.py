from django.db import migrations


def seed(apps, schema_editor):
    M = apps.get_model("gemach", "JacketModel")
    for name, code in (("קטיפה שחורה", "K"), ("שמנת", "S")):
        M.objects.filter(name=name, code="").update(code=code)


class Migration(migrations.Migration):
    dependencies = [("gemach", "0004_model_code")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
