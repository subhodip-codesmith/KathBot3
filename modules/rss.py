# coding=utf-8
import feedparser
import threading
import time
import networks
import re
import datetime

POLL_INTERVAL = 300

poller = None

class FeedPoll(threading.Thread):
    running = True
    
    def run(self):
        while self.running:
            logger.debug("Starting RSS poll.")
            subscriptions = m('datastore').query("SELECT network, channel, url, last_item, etag, last_modified FROM rss_subscriptions")
            for subscription in subscriptions:
                network, channel, url, last_item, etag, last_modified = subscription
                if not network in networks.networks:
                    continue
                
                try:
                    feed = feedparser.parse(url, etag=etag, modified=last_modified)
                    if feed.get('status', 200) == 304 or len(feed.entries) == 0:
                        logger.debug("Received HTTP 304 from %s" % url)
                        continue
                    if not feed:
                        logger.info("Received unexpected blank feed from %s (subscription for %s/%s)" % (url, network, channel))
                        continue
                    
                    latest = feed.entries[0]
                    if latest.id == last_item:
                        logger.debug("No new items in %s" % url)
                        continue
                        
                    logger.info("New item from %s!" % url)
                    
                    content = self.parse_html(latest.description)
                    if len(content) > 400:
                        content = u"%s..." % content[0:397]
                    
                    irc = networks.networks[network]
                    m('irc_helpers').message(irc, channel, u'~B[RSS]~B ~U%s – %s~U' % (feed.feed.title, feed.feed.link))
                    m('irc_helpers').message(irc, channel, '~B[RSS] %s~B' % latest.title)
                    m('irc_helpers').message(irc, channel, '~B[RSS]~B %s' % content)
                    m('irc_helpers').message(irc, channel, '~B[RSS]~B More: %s' % latest.link)
                    etag = feed.get('etag', '')
                    modified = None
                    if 'modified' in feed:
                        modified = datetime.datetime(*feed.modified[0:6])
                    last_item = latest.guid
                    m('datastore').execute('UPDATE rss_subscriptions SET etag = ?, last_modified = ?, last_item = ? WHERE url = ? AND channel = ? AND network = ?', etag, modified, last_item, url, channel, network)
                except Exception, message:
                    logger.error("Something went wrong whilst handling the feed %s: %s" % (url, message))
            
            # Wait until we go around again.
            logger.debug("Completed RSS poll.")
            time.sleep(POLL_INTERVAL)

    def parse_html(self, html):
        html = re.sub(r'(?i)</?b>', '~B', html)
        html = re.sub(r'(?i)</?[ui]>', '~U', html)
        html = re.sub(r'<img.*?src="(.+?)".*?>', r'\1', html)
        html = re.sub(r'<.*?>', '', html)
        return html

def init():
    add_hook('privmsg', privmsg)
    
    global poller
    poller = FeedPoll()
    poller.start()

def privmsg(irc, origin, args):
    irc_helpers = m('irc_helpers')
    target, command, args = irc_helpers.parse(args)
    if command == 'subscribe':
        if len(args) != 1:
            irc_helpers.message(irc, target, "You must specify a URL to subscribe to.")
            return
        url = args[0]
        feed = feedparser.parse(url)
        if feed.status < 200 or feed.status >= 300:
            irc_helpers.message(irc, target, "No feed found at %s" % url)
            return
        
        if len(feed.entries) == 0:
            irc_helpers.message(irc, target, "The specified feed is empty.")
        
        m('datastore').execute("INSERT INTO rss_subscriptions(network, channel, url) VALUES (?, ?, ?)", irc.network.name, target.lower(), url)
        
        irc_helpers.message(irc, target, "Subscribed %s to %s" % (target, feed.feed.title))

def shutdown():
    global poller
    poller.running = False
    poller = None