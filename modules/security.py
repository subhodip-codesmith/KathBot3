from fnmatch import fnmatch
from irc import User

def init():
    add_hook('message', message)
    
def message(irc, channel, origin, command, args):
    irc_helpers = m('irc_helpers')    
    if command == 'access':
        if len(args) > 0:
            nick = args[0]
            try:
                user = m('chantrack').network(irc)[channel.lower()].users[nick.lower()]
            except:
                irc_helpers.message(irc, channel, "I don't know %s's host!" % nick)
                return
        else:
            nick = origin.nick
            user = origin
        canon = get_canonical_nick(nick)
        access = get_user_access(user)
        m('irc_helpers').message(irc, channel, "Access for %s (%s!%s@%s) is level %s" % (canon, user.nick, user.ident, user.hostname, access))
    elif command == 'adduser':
        nick = args[0]
        level = int(args[1])
        host = args[2]
        userid = m('datastore').query("INSERT INTO users (nick, level) VALUES (?, ?)", nick, level)
        m('datastore').execute("INSERT INTO hosts (uid, host) VALUES (?, ?)", userid, host)
        irc_helpers.message(irc, channel, "Added user %s with access level %s." % (nick, level));
    elif command == 'cmdaccess':
        cmd = args[0]
        level = int(args[1])
        m('datastore').execute("REPLACE INTO command_access (command, level) VALUES (?, ?)", cmd, level)
        irc_helpers.message(irc, channel, "Set access level for ~B%s~B to ~B%s~B." % (cmd, level))
    elif command == 'level':
        if len(args) == 0:
            irc_helpers.message(irc, channel, "Being that we live in a totalitarian state, you need level ~B4~B clearance to ~Bdo nothing~B.")
        else:
            level = get_command_access(args[0])
            irc_helpers.message(irc, channel, "Access level for ~B%s~B is ~B%s~B" % (args[0], level))
    elif command == 'addhost':
        host = args[0]
        uid = get_user_id(origin)
        if uid is not None:
            m('datastore').execute("INSERT INTO hosts (uid, host) VALUES (?, ?)", uid, host)
            irc_helpers.message(irc, channel, "Added new host.")
        else:
            irc_helpers.message(irc, channel, "You need to actually have an account for that to work.")
    elif command == 'addalias':
        alias = args[0]
        uid = get_user_id(origin)
        if uid is not None:
            m('datastore').execute("INSERT INTO aliases (alias, canon) VALUES (?, ?)", alias, get_canonical_nick(origin.nick))
            irc_helpers.message(irc, channel, "Added new alias.")
        else:
            irc_helpers.message(irc, channel, "You need to actually have an account for that to work.")

def get_canonical_nick(nick):
    results = m('datastore').query("SELECT canon FROM aliases WHERE alias = ?", nick)
    if not results:
        return nick
    return results[0][0]

def get_user_id(user):
    nick = get_canonical_nick(user.nick)
    results = m('datastore').query("SELECT id FROM users WHERE nick = ?", nick)
    if not results:
        return None
    uid = results[0][0]
    hosts = m('datastore').query("SELECT host FROM hosts WHERE uid = ? AND (expires < DATETIME() OR expires IS NULL)", uid)
    for host in hosts:
        if fnmatch(user.hostname, host[0]):
            return uid
    
    return None

def get_user_nick(uid):
    results = m('datastore').query("SELECT nick FROM users WHERE id = ?", uid)
    if len(results) > 0:
        return results[0][0]
    else:
        return None

def get_nick_aliases(nick):
    results = m('datastore').query("SELECT alias FROM aliases WHERE canon = ?", nick)
    return [x[0] for x in results]

def get_user_access(user):
    uid = get_user_id(user)
    if uid is None:
        return 1
    return m('datastore').query("SELECT level FROM users WHERE id = ?", uid)[0][0]
    
def get_command_access(command):
    results = m('datastore').query("SELECT level FROM command_access WHERE command = ?", command)
    if not results:
        return 1
    return results[0][0]
    
def check_action_permissible(user, command):
    return get_user_access(user) >= get_command_access(command)