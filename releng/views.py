from django import forms
from django.conf import settings
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.generic.simple import direct_to_template

from .models import (Architecture, BootType, Bootloader, ClockChoice,
        Filesystem, HardwareType, InstallType, Iso, IsoType, Module, Source,
        Test)

def standard_field(model, empty_label=None, help_text=None, required=True):
    return forms.ModelChoiceField(queryset=model.objects.all(),
        widget=forms.RadioSelect(), empty_label=empty_label,
        help_text=help_text, required=required)

class TestForm(forms.ModelForm):
    iso = forms.ModelChoiceField(queryset=Iso.objects.filter(
        active=True).order_by('-id'))
    architecture = standard_field(Architecture)
    iso_type = standard_field(IsoType)
    boot_type = standard_field(BootType)
    hardware_type = standard_field(HardwareType)
    install_type = standard_field(InstallType)
    source = standard_field(Source)
    clock_choice = standard_field(ClockChoice)
    filesystem = standard_field(Filesystem,
            help_text="Verify /etc/fstab, `df -hT` output and commands like " \
            "lvdisplay for special modules.")
    modules = forms.ModelMultipleChoiceField(queryset=Module.objects.all(),
            help_text="", widget=forms.CheckboxSelectMultiple(), required=False)
    bootloader = standard_field(Bootloader,
            help_text="Verify that the entries in the bootloader config looks OK.")
    rollback_filesystem = standard_field(Filesystem,
            help_text="If you did a rollback followed by a new attempt to setup " \
            "your blockdevices/filesystems, select which option you took here.",
            empty_label="N/A (did not rollback)", required=False)
    rollback_modules = forms.ModelMultipleChoiceField(queryset=Module.objects.all(),
            help_text="If you did a rollback followed by a new attempt to setup " \
            "your blockdevices/filesystems, select which option you took here.",
            widget=forms.CheckboxSelectMultiple(), required=False)
    success = forms.BooleanField(
            help_text="Only check this if everything went fine. " \
            "If you ran into problems please create a ticket on <a " \
            "href=\"https://bugs.archlinux.org/index.php?project=6\">the " \
            "bugtracker</a> (or check that one already exists) and link to " \
            "it in the comments.",
            required=False)
    website = forms.CharField(label='',
            widget=forms.TextInput(attrs={'style': 'display:none;'}), required=False)

    class Meta:
        model = Test
        fields = ("user_name", "user_email", "iso", "architecture",
                  "iso_type", "boot_type", "hardware_type",
                  "install_type", "source", "clock_choice", "filesystem",
                  "modules", "bootloader", "rollback_filesystem",
                  "rollback_modules", "success", "comments")
        widgets = {
            "modules": forms.CheckboxSelectMultiple(),
        }

def submit_test_result(request):
    if request.POST:
        form = TestForm(request.POST)
        if form.is_valid() and request.POST['website'] == '':
            test = form.save(commit=False)
            test.ip_address = request.META.get("REMOTE_ADDR", None)
            test.save()
            form.save_m2m()
            return redirect('releng-test-thanks')
    else:
        form = TestForm()

    context = {'form': form}
    return direct_to_template(request, 'releng/add.html', context)

def calculate_option_overview(field_name):
    field = Test._meta.get_field(field_name)
    model = field.rel.to
    is_rollback = field_name.startswith('rollback_')
    option = {
        'option': model,
        'name': field_name,
        'is_rollback': is_rollback,
        'values': []
    }
    for value in model.objects.all():
        data = { 'value': value }
        if is_rollback:
            data['success'] = value.get_last_rollback_success()
            data['failure'] = value.get_last_rollback_failure()
        else:
            data['success'] = value.get_last_success()
            data['failure'] = value.get_last_failure()
        option['values'].append(data)

    return option

def test_results_overview(request):
    # data structure produced:
    # [ { option, name, is_rollback, values: [ { value, success, failure } ... ] } ... ]
    all_options = []
    fields = [ 'architecture', 'iso_type', 'boot_type', 'hardware_type',
            'install_type', 'source', 'clock_choice', 'filesystem', 'modules',
            'bootloader', 'rollback_filesystem', 'rollback_modules' ]
    for field in fields:
        all_options.append(calculate_option_overview(field))

    context = {
            'options': all_options,
            'iso_url': settings.ISO_LIST_URL,
    }
    return direct_to_template(request, 'releng/results.html', context)

def test_results_iso(request, iso_id):
    iso = get_object_or_404(Iso, pk=iso_id)
    test_list = iso.test_set.all()
    context = {
        'iso_name': iso.name,
        'test_list': test_list
    }
    return direct_to_template(request, 'releng/result_list.html', context)

def test_results_for(request, option, value):
    if option not in Test._meta.get_all_field_names():
        raise Http404
    option_model = getattr(Test, option).field.rel.to
    real_value = get_object_or_404(option_model, pk=value)
    test_list = real_value.test_set.order_by('-iso__name', '-pk')
    context = {
        'option': option,
        'value': real_value,
        'value_id': value,
        'test_list': test_list
    }
    return direct_to_template(request, 'releng/result_list.html', context)

def submit_test_thanks(request):
    return direct_to_template(request, "releng/thanks.html", None)

# vim: set ts=4 sw=4 et:
