import os,sys
import email
import email.header
from email.parser import HeaderParser
import chardet
import tempfile
import re
import importlib
import time
import logging

import converter

log = logging.getLogger(__name__)

'''
Sanitize filenames
Source: https://github.com/django/django/blob/master/django/utils/text.py
'''
def slugify(s):
    s = str(s).strip().replace(' ', '_')
    return re.sub(r'(?u)[^-\w.]', '', s)

'''
Check if the provided string matches one of the whitelist regexes
'''
def isWhitelisted(string):
    global config
    found = False
    for w in config['whitelists']:
        if re.search(w, string, re.IGNORECASE):
            found = True
            break
    return found

'''
Search for observables in the mail message buffer and build a list of found data
'''
def searchObservables(buffer, observables):
    # Observable types
    # Source: https://github.com/armbues/ioc_parser/blob/master/iocp/data/patterns.ini
    observableTypes = [
         { 'type': 'filename', 'regex': r'\b([A-Za-z0-9-_\.]+\.(exe|dll|bat|sys|htm|html|js|jar|jpg|png|vb|scr|pif|chm|zip|rar|cab|pdf|doc|docx|ppt|pptx|xls|xlsx|swf|gif))\b' },
         { 'type': 'url',      'regex': r'\b([a-z]{3,}\:\/\/[a-z0-9.\-:/?=&;]{16,})\b' },
         { 'type': 'ip',       'regex': r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b' },
         { 'type': 'fqdn',     'regex': r'\b(([a-z0-9\-]{2,}\[?\.\]?){2,}(abogado|ac|academy|accountants|active|actor|ad|adult|ae|aero|af|ag|agency|ai|airforce|al|allfinanz|alsace|am|amsterdam|an|android|ao|aq|aquarelle|ar|archi|army|arpa|as|asia|associates|at|attorney|au|auction|audio|autos|aw|ax|axa|az|ba|band|bank|bar|barclaycard|barclays|bargains|bayern|bb|bd|be|beer|berlin|best|bf|bg|bh|bi|bid|bike|bingo|bio|biz|bj|black|blackfriday|bloomberg|blue|bm|bmw|bn|bnpparibas|bo|boo|boutique|br|brussels|bs|bt|budapest|build|builders|business|buzz|bv|bw|by|bz|bzh|ca|cal|camera|camp|cancerresearch|canon|capetown|capital|caravan|cards|care|career|careers|cartier|casa|cash|cat|catering|cc|cd|center|ceo|cern|cf|cg|ch|channel|chat|cheap|christmas|chrome|church|ci|citic|city|ck|cl|claims|cleaning|click|clinic|clothing|club|cm|cn|co|coach|codes|coffee|college|cologne|com|community|company|computer|condos|construction|consulting|contractors|cooking|cool|coop|country|cr|credit|creditcard|cricket|crs|cruises|cu|cuisinella|cv|cw|cx|cy|cymru|cz|dabur|dad|dance|dating|day|dclk|de|deals|degree|delivery|democrat|dental|dentist|desi|design|dev|diamonds|diet|digital|direct|directory|discount|dj|dk|dm|dnp|do|docs|domains|doosan|durban|dvag|dz|eat|ec|edu|education|ee|eg|email|emerck|energy|engineer|engineering|enterprises|equipment|er|es|esq|estate|et|eu|eurovision|eus|events|everbank|exchange|expert|exposed|fail|farm|fashion|feedback|fi|finance|financial|firmdale|fish|fishing|fit|fitness|fj|fk|flights|florist|flowers|flsmidth|fly|fm|fo|foo|forsale|foundation|fr|frl|frogans|fund|furniture|futbol|ga|gal|gallery|garden|gb|gbiz|gd|ge|gent|gf|gg|ggee|gh|gi|gift|gifts|gives|gl|glass|gle|global|globo|gm|gmail|gmo|gmx|gn|goog|google|gop|gov|gp|gq|gr|graphics|gratis|green|gripe|gs|gt|gu|guide|guitars|guru|gw|gy|hamburg|hangout|haus|healthcare|help|here|hermes|hiphop|hiv|hk|hm|hn|holdings|holiday|homes|horse|host|hosting|house|how|hr|ht|hu|ibm|id|ie|ifm|il|im|immo|immobilien|in|industries|info|ing|ink|institute|insure|int|international|investments|io|iq|ir|irish|is|it|iwc|jcb|je|jetzt|jm|jo|jobs|joburg|jp|juegos|kaufen|kddi|ke|kg|kh|ki|kim|kitchen|kiwi|km|kn|koeln|kp|kr|krd|kred|kw|ky|kyoto|kz|la|lacaixa|land|lat|latrobe|lawyer|lb|lc|lds|lease|legal|lgbt|li|lidl|life|lighting|limited|limo|link|lk|loans|london|lotte|lotto|lr|ls|lt|ltda|lu|luxe|luxury|lv|ly|ma|madrid|maison|management|mango|market|marketing|marriott|mc|md|me|media|meet|melbourne|meme|memorial|menu|mg|mh|miami|mil|mini|mk|ml|mm|mn|mo|mobi|moda|moe|monash|money|mormon|mortgage|moscow|motorcycles|mov|mp|mq|mr|ms|mt|mu|museum|mv|mw|mx|my|mz|na|nagoya|name|navy|nc|ne|net|network|neustar|new|nexus|nf|ng|ngo|nhk|ni|ninja|nl|no|np|nr|nra|nrw|ntt|nu|nyc|nz|okinawa|om|one|ong|onl|ooo|org|organic|osaka|otsuka|ovh|pa|paris|partners|parts|party|pe|pf|pg|ph|pharmacy|photo|photography|photos|physio|pics|pictures|pink|pizza|pk|pl|place|plumbing|pm|pn|pohl|poker|porn|post|pr|praxi|press|pro|prod|productions|prof|properties|property|ps|pt|pub|pw|qa|qpon|quebec|re|realtor|recipes|red|rehab|reise|reisen|reit|ren|rentals|repair|report|republican|rest|restaurant|reviews|rich|rio|rip|ro|rocks|rodeo|rs|rsvp|ru|ruhr|rw|ryukyu|sa|saarland|sale|samsung|sarl|sb|sc|sca|scb|schmidt|schule|schwarz|science|scot|sd|se|services|sew|sexy|sg|sh|shiksha|shoes|shriram|si|singles|sj|sk|sky|sl|sm|sn|so|social|software|sohu|solar|solutions|soy|space|spiegel|sr|st|style|su|supplies|supply|support|surf|surgery|suzuki|sv|sx|sy|sydney|systems|sz|taipei|tatar|tattoo|tax|tc|td|technology|tel|temasek|tennis|tf|tg|th|tienda|tips|tires|tirol|tj|tk|tl|tm|tn|to|today|tokyo|tools|top|toshiba|town|toys|tp|tr|trade|training|travel|trust|tt|tui|tv|tw|tz|ua|ug|uk|university|uno|uol|us|uy|uz|va|vacations|vc|ve|vegas|ventures|versicherung|vet|vg|vi|viajes|video|villas|vision|vlaanderen|vn|vodka|vote|voting|voto|voyage|vu|wales|wang|watch|webcam|website|wed|wedding|wf|whoswho|wien|wiki|williamhill|wme|work|works|world|ws|wtc|wtf|xyz|yachts|yandex|ye|yoga|yokohama|youtube|yt|za|zm|zone|zuerich|zw))\b' },
         { 'type': 'domain',     'regex': r'\b(([a-z0-9\-]{2,}\[?\.\]?){1}(abogado|ac|academy|accountants|active|actor|ad|adult|ae|aero|af|ag|agency|ai|airforce|al|allfinanz|alsace|am|amsterdam|an|android|ao|aq|aquarelle|ar|archi|army|arpa|as|asia|associates|at|attorney|au|auction|audio|autos|aw|ax|axa|az|ba|band|bank|bar|barclaycard|barclays|bargains|bayern|bb|bd|be|beer|berlin|best|bf|bg|bh|bi|bid|bike|bingo|bio|biz|bj|black|blackfriday|bloomberg|blue|bm|bmw|bn|bnpparibas|bo|boo|boutique|br|brussels|bs|bt|budapest|build|builders|business|buzz|bv|bw|by|bz|bzh|ca|cal|camera|camp|cancerresearch|canon|capetown|capital|caravan|cards|care|career|careers|cartier|casa|cash|cat|catering|cc|cd|center|ceo|cern|cf|cg|ch|channel|chat|cheap|christmas|chrome|church|ci|citic|city|ck|cl|claims|cleaning|click|clinic|clothing|club|cm|cn|co|coach|codes|coffee|college|cologne|com|community|company|computer|condos|construction|consulting|contractors|cooking|cool|coop|country|cr|credit|creditcard|cricket|crs|cruises|cu|cuisinella|cv|cw|cx|cy|cymru|cz|dabur|dad|dance|dating|day|dclk|de|deals|degree|delivery|democrat|dental|dentist|desi|design|dev|diamonds|diet|digital|direct|directory|discount|dj|dk|dm|dnp|do|docs|domains|doosan|durban|dvag|dz|eat|ec|edu|education|ee|eg|email|emerck|energy|engineer|engineering|enterprises|equipment|er|es|esq|estate|et|eu|eurovision|eus|events|everbank|exchange|expert|exposed|fail|farm|fashion|feedback|fi|finance|financial|firmdale|fish|fishing|fit|fitness|fj|fk|flights|florist|flowers|flsmidth|fly|fm|fo|foo|forsale|foundation|fr|frl|frogans|fund|furniture|futbol|ga|gal|gallery|garden|gb|gbiz|gd|ge|gent|gf|gg|ggee|gh|gi|gift|gifts|gives|gl|glass|gle|global|globo|gm|gmail|gmo|gmx|gn|goog|google|gop|gov|gp|gq|gr|graphics|gratis|green|gripe|gs|gt|gu|guide|guitars|guru|gw|gy|hamburg|hangout|haus|healthcare|help|here|hermes|hiphop|hiv|hk|hm|hn|holdings|holiday|homes|horse|host|hosting|house|how|hr|ht|hu|ibm|id|ie|ifm|il|im|immo|immobilien|in|industries|info|ing|ink|institute|insure|int|international|investments|io|iq|ir|irish|is|it|iwc|jcb|je|jetzt|jm|jo|jobs|joburg|jp|juegos|kaufen|kddi|ke|kg|kh|ki|kim|kitchen|kiwi|km|kn|koeln|kp|kr|krd|kred|kw|ky|kyoto|kz|la|lacaixa|land|lat|latrobe|lawyer|lb|lc|lds|lease|legal|lgbt|li|lidl|life|lighting|limited|limo|link|lk|loans|london|lotte|lotto|lr|ls|lt|ltda|lu|luxe|luxury|lv|ly|ma|madrid|maison|management|mango|market|marketing|marriott|mc|md|me|media|meet|melbourne|meme|memorial|menu|mg|mh|miami|mil|mini|mk|ml|mm|mn|mo|mobi|moda|moe|monash|money|mormon|mortgage|moscow|motorcycles|mov|mp|mq|mr|ms|mt|mu|museum|mv|mw|mx|my|mz|na|nagoya|name|navy|nc|ne|net|network|neustar|new|nexus|nf|ng|ngo|nhk|ni|ninja|nl|no|np|nr|nra|nrw|ntt|nu|nyc|nz|okinawa|om|one|ong|onl|ooo|org|organic|osaka|otsuka|ovh|pa|paris|partners|parts|party|pe|pf|pg|ph|pharmacy|photo|photography|photos|physio|pics|pictures|pink|pizza|pk|pl|place|plumbing|pm|pn|pohl|poker|porn|post|pr|praxi|press|pro|prod|productions|prof|properties|property|ps|pt|pub|pw|qa|qpon|quebec|re|realtor|recipes|red|rehab|reise|reisen|reit|ren|rentals|repair|report|republican|rest|restaurant|reviews|rich|rio|rip|ro|rocks|rodeo|rs|rsvp|ru|ruhr|rw|ryukyu|sa|saarland|sale|samsung|sarl|sb|sc|sca|scb|schmidt|schule|schwarz|science|scot|sd|se|services|sew|sexy|sg|sh|shiksha|shoes|shriram|si|singles|sj|sk|sky|sl|sm|sn|so|social|software|sohu|solar|solutions|soy|space|spiegel|sr|st|style|su|supplies|supply|support|surf|surgery|suzuki|sv|sx|sy|sydney|systems|sz|taipei|tatar|tattoo|tax|tc|td|technology|tel|temasek|tennis|tf|tg|th|tienda|tips|tires|tirol|tj|tk|tl|tm|tn|to|today|tokyo|tools|top|toshiba|town|toys|tp|tr|trade|training|travel|trust|tt|tui|tv|tw|tz|ua|ug|uk|university|uno|uol|us|uy|uz|va|vacations|vc|ve|vegas|ventures|versicherung|vet|vg|vi|viajes|video|villas|vision|vlaanderen|vn|vodka|vote|voting|voto|voyage|vu|wales|wang|watch|webcam|website|wed|wedding|wf|whoswho|wien|wiki|williamhill|wme|work|works|world|ws|wtc|wtf|xyz|yachts|yandex|ye|yoga|yokohama|youtube|yt|za|zm|zone|zuerich|zw))\b' },
         { 'type': 'mail',   'regex': r'\b([a-z][_a-z0-9-.+]+@[a-z0-9-.]+\.[a-z]+)\b' },
         { 'type': 'hash',   'regex': r'\b([a-f0-9]{32}|[A-F0-9]{32})\b' },
         { 'type': 'hash',   'regex': r'\b([a-f0-9]{40}|[A-F0-9]{40})\b' },
         { 'type': 'hash',   'regex': r'\b([a-f0-9]{64}|[A-F0-9]{64})\b' }
         ]

    # Add custom observables if any
    for o in config['customObservables']:
        observableTypes.append({ 'type': o, 'regex': config['customObservables'][o] })

    for o in observableTypes:
        for match in re.findall(o['regex'], buffer, re.MULTILINE|re.IGNORECASE):
            # Bug: If match is a tuple (example for domain or fqdn), use the 1st element
            if type(match) is tuple:
                match = match[0]
            observables.append({ 'type': o['type'], 'value': match })
    return observables

'''
Main handler to
* parse the mail message and its attachments
* forward the parsed data to a distinct
  TheHive "mail handler" based on the email
  subject to create the desired TheHive objects:
  * Cases
  * Alerts
  * etc.

Return 'TRUE' is successfully processed otherwise 'FALSE'
'''
def submitEmailToTheHive(messageObj):
    # Decode email
    decode = email.header.decode_header(messageObj['From'])[0]
    if decode[1] is not None:
        fromField = decode[0].decode(decode[1])
    else:
        fromField = str(decode[0])
    decode = email.header.decode_header(messageObj['Subject'])[0]
    if decode[1] is not None:
        subjectField = decode[0].decode(decode[1])
    else:
        subjectField = str(decode[0])
    log.info("%s.submitEmailToTheHive()::From: %s Subject: %s" % (__name__, fromField, subjectField))

    attachments = []
    observables = []

    # Extract SMTP headers and search for observables
    parser = HeaderParser()
    headers = parser.parsestr(messageObj.as_string())
    headers_string = ''
    i = 0
    while  i < len(headers.keys()):
        headers_string = headers_string + headers.keys()[i] + ': ' + headers.values()[i] + '\n'
        i+=1
    # Temporary disabled
    # observables = searchObservables(headers_string, observables)
    log.info('%s.submitEmailToTheHive()::Headers[Date]: %s' % (__name__, headers['Date']))
    emailDate = email.utils.mktime_tz( 
        email.utils.parsedate_tz( headers['Date'] )
    ) * 1000
    log.debug('%s.submitEmailToTheHive()::Date: %s' % (__name__, emailDate))
    log.debug('%s.submitEmailToTheHive()::Date from int(time.time()) * 1000: %s' % (__name__, int(time.time()) * 1000))

    body = ''
    mdBody = 'Headers:\n```\n'+headers_string+'\n```\n----\n'
    i = 0
    for part in messageObj.walk():
        if part.get_content_type() == "text/plain" and part.get_content_disposition() != "attachment":
            try:
                body    = body + "\nMessage Part " + str(i) + ":\nContent-Type: " + part.get_content_type() + "\n" + part.get_payload(decode=True).decode()
                mdBody  = mdBody + "\nMessage Part " + str(i) + ":\nContent-Type: `" + part.get_content_type() + "`:\n```\n" + part.get_payload(decode=True).decode() + "\n```"
            except UnicodeDecodeError:
                body = part.get_payload(decode=True).decode('ISO-8859-1')
                mdBody = mdBody + "```" + part.get_payload(decode=True).decode('ISO-8859-1') + "```"
            observables.extend( searchObservables(body, observables) )

        elif part.get_content_type() == "text/html":
            try:
                html = part.get_payload(decode=True).decode()
            except UnicodeDecodeError:
                html = part.get_payload(decode=True).decode('ISO-8859-1')
            observables.extend( searchObservables(html, observables) )

        else:
            # Extract MIME parts
            filename = part.get_filename()
            mimetype = part.get_content_type()
            if filename and mimetype:
                if (
                    mimetype in config['caseFiles'] or not config['caseFiles']
                ) and not isWhitelisted( filename ):
                    log.info("%s.submitEmailToTheHive()::Found attachment: %s (%s)" % (__name__, filename, mimetype))
                    # Decode the attachment and save it in a temporary file
                    charset = part.get_content_charset()
                    if charset is None:
                        charset = chardet.detect(bytes(part))['encoding']
                    # Get filename extension to not break TheHive analysers (see Github #11)
                    fname, fextension = os.path.splitext(filename)
                    fd, path = tempfile.mkstemp(prefix=slugify(fname) + "_", suffix=fextension)
                    try:
                        with os.fdopen(fd, 'w+b') as tmp:
                            tmp.write(part.get_payload(decode=1))
                        attachments.append( path )
                    except OSError as e:
                        log.error("%s.submitEmailToTheHive()::Cannot dump attachment to %s: %s" % (__name__, path, e.errno))
                        return False
                else:
                    body    = body + "\n----\nIMAP-2-THEHIVE NOTICE: Found not allowed attachment '" +filename+ "' of Content-Type: " + mimetype
                    mdBody  = mdBody + "\n----\nIMAP-2-THEHIVE NOTICE: Found not allowed attachment '" +filename+ "' of Content-Type: `" + mimetype + "`"

        i = i + 1

    # Add the original email message also as attachment:
    if config['customAttachments']['attachOriginalEmail']:
        fd, path = tempfile.mkstemp(prefix="original_email_", suffix=".eml")
        log.info("%s.submitEmailToTheHive()::Adding original email as '*.eml' attachment (tmp path:%s)..." % (__name__, path))
        try:
            with os.fdopen(fd, 'w+b') as tmp:
                tmp.write( messageObj.as_bytes() )
            attachments.append( path )
        except OSError as e:
            log.error("%s.submitEmailToTheHive()::Cannot original email as '*.eml' attachment to %s: %s" % (__name__, path,e.errno))
            return False

    # Cleanup observables (remove duplicates)
    new_observables = []
    for o in observables:
        if not {'type': o['type'], 'value': o['value'] } in new_observables:
            # Is the observable whitelisted?
            if isWhitelisted(o['value']):
                log.debug('%s.submitEmailToTheHive()::Skipping whitelisted observable: %s' % (__name__, o['value']))
            else:
                new_observables.append({ 'type': o['type'], 'value': o['value'] })
                log.debug('%s.submitEmailToTheHive()::Found observable %s: %s' % (__name__, o['type'], o['value']))
        else:
            log.info('%s.submitEmailToTheHive()::Ignoring duplicate observable: %s' % (__name__, o['value']))
    log.info("%s.submitEmailToTheHive()::Removed duplicate observables: %d -> %d" % (__name__, len(observables), len(new_observables)))
    observables = new_observables

    '''
    Convert email into TheHive data with the first (1st) matching converter...
    '''
    for conv in converter.CONVERTERS:
        result = conv(
            config,
            subjectField,
            body,
            mdBody,
            emailDate,
            fromField,
            observables,
            attachments
        )
        if result is not None:
            return result

'''
Setup the module
'''
def init(configObj):
    global config
    config = configObj
