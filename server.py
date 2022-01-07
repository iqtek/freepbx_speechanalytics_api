from typing import Optional
from fastapi import FastAPI, Request, Header, Response, HTTPException
from pydantic import BaseModel
from pydub import AudioSegment
from icecream import ic
import pymysql.cursors
import accept_types
import requests
import os
import datetime
import time
import struct
import settings as cfg

app = FastAPI()


def write_header(_bytes, _nchannels, _sampwidth, _framerate):
    _nframes = len(_bytes) // (_nchannels * _sampwidth)
    _datalength = _nframes * _nchannels * _sampwidth
    bytes_to_add = b'RIFF' + struct.pack('<L4s4sLHHLLHH4s',
        36 + _datalength, b'WAVE', b'fmt ', 16,
        0x0001, _nchannels, _framerate,
        _nchannels * _framerate * _sampwidth,
        _nchannels * _sampwidth,
        _sampwidth * 8, b'data')

    bytes_to_add += struct.pack('<L', _datalength)
    return bytes_to_add + _bytes

def check_auth(authorization):
    if authorization == None:
        raise HTTPException(status_code=403, detail="Forbidden")
    if authorization != f"Bearer {cfg.bearer_token}":
        raise HTTPException(status_code=403, detail="Forbidden")

# GET /calls?date_from=1527847200&date_till=1528641300
@app.get("/calls")
async def get_calls(date_from: int = 0, date_till: int = 0, authorization: Optional[str] = Header(None)):
    check_auth(authorization)
    connection = pymysql.connect(host=cfg.mysql_host,
        user=cfg.mysql_user,
        password=cfg.mysql_password,
        db=cfg.mysql_db,
        cursorclass=pymysql.cursors.DictCursor)

    devices = []
    with connection.cursor() as cursor:
        sql = """select dial from asterisk.devices where tech in ('sip','pjsip');"""
        cursor.execute(sql)
        for d in cursor.fetchall():
            devices.append(d['dial'])

    calls = []
    with connection.cursor() as cursor:
        sql = """SELECT * FROM asteriskcdrdb.cdr WHERE addtime BETWEEN from_unixtime(%s) AND from_unixtime(%s)"""
        cursor.execute(sql, (date_from, date_till))
        result = cursor.fetchall()
    if result == None:
        return {"calls": calls}

    calls = {}
    for r in result:
        if len(r['dst'])>0 and r['dst'][0] == '*':
            continue
        if int(r['billsec']) < cfg.billsec_min:
            continue

        call = {}
        call['id'] = r['linkedid']
        call['date'] = int(time.mktime(r['calldate'].timetuple()))
        call['duration_answer'] = r['billsec']
        call['status'] = 'ACCEPTED' if (r['disposition'] == 'ANSWERED') else 'REJECTED'
        src_device = r['channel'].split('-',1)[0]
        dst_device = r['dstchannel'].split('-',1)[0]
        if (src_device in devices) and (dst_device in devices):
            if not cfg.recognize_local:
                continue
            call['type'] = "LOCAL"
            call['phone_number_client'] = src_device.split('/',1)[1]
            call['phone_number_operator'] = dst_device.split('/',1)[1]
        elif dst_device in devices:
            if not cfg.recognize_in:
                continue
            if ('*' not in cfg.did_filter) and (r['did'] not in cfg.did_filter):
                continue
            call['type'] = "INCOMING"
            call['phone_number_client'] = r['src']
            call['phone_number_operator'] = dst_device.split('/',1)[1]
        elif src_device in devices:
            if not cfg.recognize_out:
                continue
            call['type'] = "OUTGOING"
            call['phone_number_client'] = r['dst']
            call['phone_number_operator'] = src_device.split('/',1)[1]
        else:
            continue

        if (calls.get(call['id'], None) != None):
            if (calls[call['id']]['status'] == "REJECTED") and (call['status'] == 'ACCEPTED'):
                calls[call['id']] = call
        else:
            calls[call['id']] = call

    print(f"Calls:" + str(len(calls)))
    return {"calls": list(calls.values())}


# GET /recording?call_id=1639732577.13820
@app.get("/recording")
async def get_recording(call_id: str, authorization: Optional[str] = Header(None)):
    check_auth(authorization)
    connection = pymysql.connect(host=cfg.mysql_host,
        user=cfg.mysql_user,
        password=cfg.mysql_password,
        db=cfg.mysql_db,
        cursorclass=pymysql.cursors.DictCursor)

    with connection.cursor() as cursor:
        sql = """SELECT calldate,recordingfile FROM asteriskcdrdb.cdr WHERE linkedid=%s and recordingfile!='' LIMIT 1"""
        cursor.execute(sql, (call_id))
        res = cursor.fetchone()
    if res == None:
        raise HTTPException(status_code=404, detail="Item not found")
    recfile = res['calldate'].strftime(cfg.recording_path) + res['recordingfile']
    format = recfile.rsplit('.', maxsplit=1)[1]
    if (format != 'wav'):
        raise HTTPException(status_code=415, detail="Unsupported Media Type")
    recfile_in = recfile.rsplit('.', maxsplit=1)[0] + f"-in.{format}"
    recfile_out = recfile.rsplit('.', maxsplit=1)[0] + f"-out.{format}"
    if os.path.isfile(recfile_in) and os.path.isfile(recfile_out):
        l_channel = AudioSegment.from_wav(recfile_in)
        r_channel = AudioSegment.from_wav(recfile_out)
        offset = AudioSegment.silent(duration=abs(len(l_channel) - len(r_channel)), frame_rate=r_channel.frame_rate)
        if len(l_channel) > len(r_channel):
            r_channel = r_channel + offset
        if len(r_channel) > len(l_channel):
            l_channel = l_channel + offset
        sound = AudioSegment.from_mono_audiosegments(l_channel, r_channel)
    elif os.path.isfile(recfile):
        sound = AudioSegment.from_wav(recfile)
    else:
        raise HTTPException(status_code=404, detail="Not Found")
    return Response(content=write_header(sound.raw_data, sound.channels, sound.sample_width, sound.frame_rate), media_type=cfg.wav_mime_type, headers={
            'Content-Disposition': f"attachment;filename={res['recordingfile']}"})

# GET /operators
@app.get("/operators")
async def get_operators(authorization: Optional[str] = Header(None)):
    check_auth(authorization)
    connection = pymysql.connect(host=cfg.mysql_host,
        user=cfg.mysql_user,
        password=cfg.mysql_password,
        db=cfg.mysql_db,
        cursorclass=pymysql.cursors.DictCursor)

    operators = []
    with connection.cursor() as cursor:
        sql = """select extension as phone_number,name from asterisk.users;"""
        cursor.execute(sql)
        operators = cursor.fetchall()

    return {"operators": operators}
