# coding:utf-8

from celery import Celery, platforms
from celery.schedules import crontab
from datetime import timedelta
# celery beat

import os
import sys
import shlex
import subprocess
import pymongo
import datetime
from .job import daily_job, realtime_job
platforms.C_FORCE_ROOT = True  # 加上这一行
client_qa = pymongo.MongoClient().quantaxis.joblog
client_joblist = pymongo.MongoClient().quantaxis.joblist
client_qa.create_index('filename')


schedule_client = pymongo.MongoClient().quantaxis.schedule
"""schedule



1. create time
2. lastupdatetime
3. command
4. 

"""


class celeryconfig():
    broker_url = "pyamqp://"   # 使用redis存储任务队列
    RESULT_BACKEND = "rpc://"  # 使用redis存储结果
    task_default_queue = 'default'
    task_serializer = 'json'
    result_serializer = 'json'
    accept_content = ['json', 'pickle']
    timezone = "Asia/Shanghai"  # 时区设置
    enable_utc = False
    worker_hijack_root_logger = False  # celery默认开启自己的日志，可关闭自定义日志，不关闭自定义日志输出为空
    result_expires = 60 * 60 * 24  # 存储结果过期时间（默认1天）
    imports = (
        "quantaxis_run"
    )

    beat_schedule = {
        'daily': {
            'task': 'quantaxis_run.monitor_daily',
            'schedule': crontab(minute='50', hour='8,12,15,20')
        },
        'trading': {
            'task': 'quantaxis_run.monitor_trading',
            'schedule': timedelta(seconds=10)
        },
    }


app = Celery('quantaxis_run', backend='rpc://', broker='pyamqp://')
app.config_from_object(celeryconfig)

# A task being bound means the first argument to the task will always be the task instance (self), just like Python bound methods:


@app.task(bind=True)
def quantaxis_run(self, shell_cmd, program='python'):

    filename = shell_cmd
    shell_cmd = '{} "{}"'.format(program, shell_cmd)

    client_qa.insert({
        'job_id': str(self.request.id),
        'source': program,
        'filename': filename,
        'time': str(datetime.datetime.now()),
        'message': 'start',
        'status': 'start'})
    client_joblist.insert(
        {'program': program, 'files': filename, 'status': 'running', 'job_id': str(self.request.id)})
    cmd = shlex.split(shell_cmd)
    p = subprocess.Popen(
        cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    while p.poll() is None:
        line = p.stdout.readline()
        line = line.strip()
        if line:
            client_qa.insert({
                'job_id': str(self.request.id),
                'filename': filename,
                'time': str(datetime.datetime.now()),
                'message': str(line),
                'status': 'running'})
    if p.returncode == 0:
        client_qa.insert({
            'job_id': str(self.request.id),
            'filename': filename,
            'time': str(datetime.datetime.now()),
            'message': 'backtest run  success',
            'status': 'success'})
        client_joblist.find_and_modify({'job_id': str(self.request.id)}, {
                                       '$set': {'status': 'success'}})
    else:
        client_qa.insert({
            'job_id': str(self.request.id),
            'filename': filename,
            'time': str(datetime.datetime.now()),
            'message': str(p.returncode),
            'status': 'failed'})


@app.task(bind=True)
def run_shell(self, shell_cmd):

    filename = shell_cmd
    shell_cmd = '{}'.format(shell_cmd)

    client_qa.insert({
        'job_id': str(self.request.id),
        'source': shell_cmd,
        'filename': filename,
        'time': str(datetime.datetime.now()),
        'message': 'start',
        'status': 'start'})
    client_joblist.insert(
        {'program': shell_cmd, 'files': filename, 'status': 'running', 'job_id': str(self.request.id)})
    cmd = shlex.split(shell_cmd)
    p = subprocess.Popen(
        cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    while p.poll() is None:
        line = p.stdout.readline()
        line = line.strip()
        if line:
            client_qa.insert({
                'job_id': str(self.request.id),
                'filename': filename,
                'time': str(datetime.datetime.now()),
                'message': str(line),
                'status': 'running'})
    if p.returncode == 0:
        client_qa.insert({
            'job_id': str(self.request.id),
            'filename': filename,
            'time': str(datetime.datetime.now()),
            'message': 'backtest run  success',
            'status': 'success'})
        client_joblist.find_and_modify({'job_id': str(self.request.id)}, {
                                       '$set': {'status': 'success'}})
    else:
        client_qa.insert({
            'job_id': str(self.request.id),
            'filename': filename,
            'time': str(datetime.datetime.now()),
            'message': str(p.returncode),
            'status': 'failed'})


@app.task(bind=True)
def monitor_daily(self):
    """
    scan work/ report
    """
    daily_job().execute()


@app.task(bind=True)
def monitor_trading(self):
    realtime_job().execute()
