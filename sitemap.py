#!/usr/bin/env python
# -*- coding: utf-8 -*- 

# A little script to construct sitemap of the website.
# Follow the specification of XML Sitemap
# Very ugly now. Need further revision
# The script should be set up as a scheduled task.

from datetime import datetime
import StringIO
from ftplib import FTP

from app import app
from models import *

def write_tag(output, url, img=None, lastmod=None, changefreq="yearly", priority=0.5):
    print >>output, '<url>'
    print >>output, '<loc>%s</loc>' % url
    if lastmod:
        print >>output, '<lastmod>%s</lastmod>' % lastmod
    print >>output, '<changefreq>%s</changefreq>' % changefreq
    print >>output, '<priority>%s</priority>' % priority
    if img:
        print >>output, '<image:image>'
        print >>output, '<image:loc>http://ihome.ust.hk/~su_film/asset/upload/%s</image:loc>' % img
        print >>output, '</image:image>'
    print >>output, '</url>'

def priority_calc(delta, upbound):
    return (7 ** 1.8) * upbound / ((delta.days + 7) ** 1.8)

def main():
    output = StringIO.StringIO()
    print >>output, '<?xml version="1.0" encoding="UTF-8"?>'
    print >>output, '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">'

    # home
    write_tag(output, "http://ihome.ust.hk/~su_film/", changefreq="daily", priority=1.0)
    write_tag(output, "http://ihome.ust.hk/~su_film/#!home", changefreq="daily", priority=1.0)
    query = News.select()
    for news in query:
        log = Log.select().where(Log.model == 'News', Log.model_refer == news.id).get()
        log_time = log.created_at.strftime('%Y-%m-%dT%H:%M:%S+08:00')
        delta = datetime.now() - news.create_log.created_at
        write_tag(output, "http://ihome.ust.hk/~su_film/#!news/%d/" % news.id, lastmod=log_time, changefreq="monthly", priority=priority_calc(delta, 0.3))

    #rfs
    write_tag(output, "http://ihome.ust.hk/~su_film/#!show", priority=0.8)

    #liba
    write_tag(output, "http://ihome.ust.hk/~su_film/#!library", priority=0.8)
    query = Disk.select()
    for disk in query:
        log = Log.select().where(Log.model == 'Disk', Log.model_refer == disk.id).get()
        log_time = log.created_at.strftime('%Y-%m-%dT%H:%M:%S+08:00')
        delta = datetime.now() - disk.create_log.created_at
        write_tag(output, "http://ihome.ust.hk/~su_film/#!library/%d/" % disk.id, lastmod=log_time, changefreq="weekly", priority=priority_calc(delta, 0.5))

    #ticket
    tlog = Log.select().where(Log.model == 'PreviewShowTicket').get()
    tlog_time = tlog.created_at.strftime('%Y-%m-%dT%H:%M:%S+08:00')
    write_tag(output, "http://ihome.ust.hk/~su_film/#!ticket", lastmod=tlog_time, changefreq="weekly", priority=0.8)

    #document
    tlog = Log.select().where(Log.model == 'Document').get()
    tlog_time = tlog.created_at.strftime('%Y-%m-%dT%H:%M:%S+08:00')
    write_tag(output, "http://ihome.ust.hk/~su_film/#!document", lastmod=tlog_time, changefreq="yearly", priority=0.2)

    #publication
    if (Log.select().where(Log.model == 'Publication').exists()):
        tlog = Log.select().where(Log.model == 'Publication').get()
        tlog_time = tlog.created_at.strftime('%Y-%m-%dT%H:%M:%S+08:00')
        write_tag(output, "http://ihome.ust.hk/~su_film/#!publication", lastmod=tlog_time, changefreq="monthly", priority=0.7)

    #aboutus
    write_tag(output, "http://ihome.ust.hk/~su_film/#!aboutus", priority=0.7)

    print >>output, "</urlset>"

    output.seek(0)
    conn = FTP('ihome.ust.hk', app.config['SOCIETY_USERNAME'], app.config['SOCIETY_PASSWORD'])
    conn.cwd('/')
    conn.storbinary("STOR sitemap.xml", output)
    conn.quit()
    output.close()

if __name__ == '__main__':
    main()
