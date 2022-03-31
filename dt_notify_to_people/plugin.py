"""
  @Project     : dt_notify_to_people
  @Time        : 2022/02/24 13:35:48
  @File        : __init__.py
  @Author      : MrChen
  @Software    : VSCode
  @Desc        : 
"""


import requests
import six
from sentry.plugins.bases import notify
from sentry.utils import json
from sentry.integrations import FeatureDescription, IntegrationFeatures
from sentry_plugins.base import CorePluginMixin
from django.conf import settings


class DingTalkNotifyPlugin(CorePluginMixin, notify.NotificationPlugin):
    title = "钉钉群告警通知"
    slug = "dtnotifytopeople"
    description = "钉钉群告警通知，可以通知到具体人员。【主要告警字段：项目名称、查看详情、具体报错】"
    conf_key = "dtnotifytopeople"
    required_field = "webhook"
    author = "Mo"
    author_url = "https://github.com/M-Davinci/dt_notify_to_people"
    version = "1.0.5"
    resource_links = [
        ("Report Issue", "https://github.com/M-Davinci/dt_notify_to_people/issues"),
        ("View Source", "https://github.com/M-Davinci/dt_notify_to_people"),
    ]

    feature_descriptions = [
        FeatureDescription(
            """
                Configure rule based Dingtalk notifications to automatically be posted into a
                specific channel.
                """,
            IntegrationFeatures.ALERT_RULE,
        )
    ]

    def is_configured(self, project):
        return bool(self.get_option("webhook", project))

    def get_config(self, project, **kwargs):
        return [
            {
                "name": "webhook",
                "label": "webhook",
                "type": "textarea",
                "placeholder": "https://oapi.dingtalk.com/robot/send?access_token=**********",
                "required": True,
                "help": "添加告警群URL(一行一个)。",
                "default": self.set_default(project, "webhook", "DINGTALK_WEBHOOK"),
            },
            {
                "name": "custom_keyword",
                "label": "告警标题",
                "type": "string",
                "placeholder": "e.g. [Sentry告警] 标题",
                "required": False,
                "help": "填写告警标题，需包含钉钉群里设置的关键字，否则接收不到告警信息。",
                "default": self.set_default(
                    project, "custom_keyword", "DINGTALK_CUSTOM_KEYWORD"
                ),
            },
            {
                "name": "phones",
                "label": "通知人员",
                "type": "string",
                "placeholder": "e.g. 18267885654,18267885654",
                "required": False,
                "help": "通知具体人员(使用逗号隔开手机号码)。",
                "default": self.set_default(
                    project, "phones", "DINGTALK_PHONES"
                ),
            },
        ]

    def set_default(self, project, option, env_var):
        if self.get_option(option, project) != None:
            return self.get_option(option, project)
        if hasattr(settings, env_var):
            return six.text_type(getattr(settings, env_var))
        return None

    def split_urls(self, value):
        if not value:
            return ()
        return filter(bool, (url.strip() for url in value.splitlines()))
    
    def get_webhook_urls(self, project):
        return self.split_urls(self.get_option("webhook", project))

    def notify(self, notification, raise_exception=False):
        event = notification.event
        group = event.group
        project = group.project
        self._post(group, project)

    def notify_about_activity(self, activity):
        project = activity.project
        group = activity.group
        self._post(group, project)

    def _post(self, group, project):
        custom_keyword = self.get_option("custom_keyword", project)
        phones = self.get_option("phones", project)

        issue_link = group.get_absolute_url(params={"referrer": "dingtalknotify"})
        issue_link = issue_link.replace('https', 'http')

        payload = f"## {custom_keyword}\n\n" if custom_keyword else ""
        payload = f"{payload} > 项目名称: {project.name} \n\n"
        payload = f"{payload} > 查看详情: <font color=blue>[{group.title}]({issue_link})</font> \n\n"
        payload = f"{payload} > 具体报错: {group.message} \n\n"

        headers = {
            "Content-type": "application/json",
            "Accept": "text/plain",
            "charset": "utf8"
        }

        # 一次通知多人，传递过来的电话号码为字符串拼接，形如：'187888823,1234866899'
        notify_user = []
        phone = ''
        if phones is not None:
            phone = phones.split(',')
            for i in phone:
                try:
                    notify_user.append(int(i))
                except Exception as wrong:
                    return "{\"error\":\"参数不是数字！\"}"

        data = {
            "msgtype": "markdown",
            "markdown": {
                "title": group.title,
                "text": payload + '\n\n' + '@' + '@'.join(phone)
            },
            "at": {
                "atMobiles": notify_user,
                "isAtAll": False
            }

        }

        for webhook_url in self.get_webhook_urls(group.project):
            requests.post(webhook_url, data=json.dumps(data), headers=headers)
