# card representation
# -*- coding: utf-8
import re
import random

import utils
import transforms
from manalib import Manacost, Manatext
from titlecase import titlecase

# Some text prettification stuff that people may not have installed
try:
    from titlecase import titlecase
except ImportError:
    def titlecase(s):
        return s.title()

try:
    import textwrap
    import nltk.data
    sent_tokenizer = nltk.data.load('tokenizers/punkt/english.pickle')
    # This crazy thing is actually invoked as an unpass, so newlines are still
    # encoded.
    def sentencecase(s):
        s = s.replace(utils.x_marker, utils.reserved_marker)
        lines = s.split(utils.newline)
        clines = []
        for line in lines:
            if line:
                sentences = sent_tokenizer.tokenize(line)
                clines += [' '.join([sent.capitalize() for sent in sentences])]
        return utils.newline.join(clines).replace(utils.reserved_marker, utils.x_marker)
except ImportError:
    def sentencecase(s):
        return s

# These are used later to determine what the fields of the Card object are called.
# Define them here because they have nothing to do with the actual format.
field_name = 'name'
field_rarity = 'rarity'
field_cost = 'cost'
field_supertypes = 'supertypes'
field_types = 'types'
field_subtypes = 'subtypes'
field_loyalty = 'loyalty'
field_pt = 'pt'
field_text = 'text'
field_other = 'other' # it's kind of a pseudo-field

# Import the labels, because these do appear in the encoded text.
field_label_name = utils.field_label_name
field_label_rarity = utils.field_label_rarity
field_label_cost = utils.field_label_cost
field_label_supertypes = utils.field_label_supertypes
field_label_types = utils.field_label_types
field_label_subtypes = utils.field_label_subtypes
field_label_loyalty = utils.field_label_loyalty
field_label_pt = utils.field_label_pt
field_label_text = utils.field_label_text

fieldnames = [
    field_name,
    field_rarity,
    field_cost,
    field_supertypes,
    field_types,
    field_subtypes,
    field_loyalty,
    field_pt,
    field_text,
]

fmt_ordered_default = [
    field_name,
    field_supertypes,
    field_types,
    field_loyalty,
    field_subtypes,
    field_rarity,
    field_pt,
    field_cost,
    field_text,
]

fmt_labeled_default = {
    field_name : field_label_name,
    field_rarity : field_label_rarity,
    field_cost : field_label_cost,
    field_supertypes : field_label_supertypes,
    field_types : field_label_types,
    field_subtypes : field_label_subtypes,
    field_loyalty : field_label_loyalty,
    field_pt : field_label_pt,
    field_text : field_label_text,
}

# sanity test if a card's fields look plausible
def fields_check_valid(fields):
    # all cards must have a name and a type
    if not field_name in fields:
        return False
    if not field_types in fields:
        return False
    # creatures have p/t, other things don't
    iscreature = False
    for idx, value in fields[field_types]:
        if 'creature' in value:
            iscreature = True
    if iscreature:
        return field_pt in fields
    else:
        return not field_pt in fields


def uppercaseNewLineAndFullstop(string):
    # ok, let's capitalize every letter after a full stop and newline. 
    # first let's find all indices of '.' and '\n'
    indices = [0] # initialise with 0, since we always want to capitalise the first letter.
    newlineIndices = [0] # also need to keep track of pure newlines (for planeswalkers).
    for i in range (len(string)):
        if string[i] == '\n':
            indices.append(i + 1) # we want the index of the letter after the \n, so add one.
            newlineIndices.append(i + 1)
        if string[i] == '.' or string[i] == "=": # also handle the choice bullets.
            indices.append(i + 2) # we want the index of the letter after the ., so we need to count the space as well.
    indexSet = set(indices) # convert it to a set for the next part; the capitalisation.
    return "".join(c.upper() if i in indexSet else c for i, c in enumerate(string))

# These functions take a bunch of source data in some format and turn
# it into nicely labeled fields that we know how to initialize a card from.
# Both return a dict that maps field names to lists of possible values,
# paired with the index that we read that particular field value from.
# So, {fieldname : [(idx, value), (idx, value)...].
# Usually we want these lists to be length 1, but you never know.

# Of course to make things nice and simple, that dict is the third element
# of a triple that reports parsing success and valid success as its 
# first two elements.

# This whole things assumes the json format of mtgjson.com.

# Here's a brief list of relevant fields:
# name - string
# names - list (used for split, flip, and double-faced)
# manaCost - string
# cmc - number
# colors - list
# type - string (the whole big long damn thing)
# supertypes - list
# types - list
# subtypes - list
# text - string
# power - string
# toughness - string
# loyalty - number

# And some less useful ones, in case they're wanted for something:
# layout - string
# rarity - string
# flavor - string
# artist - string
# number - string
# multiverseid - number
# variations - list
# imageName - string
# watermark - string
# border - string
# timeshifted - boolean
# hand - number
# life - number
# reserved - boolean
# releaseDate - string
# starter - boolean

def fields_from_json(src_json):
    parsed = True
    valid = True
    fields = {}

    # we hardcode in what the things are called in the mtgjson format
    if 'name' in src_json:
        name_val = src_json['name'].lower()
        name_orig = name_val
        name_val = transforms.name_pass_1_sanitize(name_val)
        name_val = utils.to_ascii(name_val)
        fields[field_name] = [(-1, name_val)]
    else:
        name_orig = ''
        parsed = False

    # return the actual Manacost object
    if 'manaCost' in src_json:
        cost =  Manacost(src_json['manaCost'], fmt = 'json')
        valid = valid and cost.valid
        parsed = parsed and cost.parsed
        fields[field_cost] = [(-1, cost)]

    if 'supertypes' in src_json:
        fields[field_supertypes] = [(-1, map(lambda s: utils.to_ascii(s.lower()), 
                                             src_json['supertypes']))]

    if 'types' in src_json:
        fields[field_types] = [(-1, map(lambda s: utils.to_ascii(s.lower()), 
                                        src_json['types']))]
    else:
        parsed = False

    if 'subtypes' in src_json:
        fields[field_subtypes] = [(-1, map(lambda s: utils.to_ascii(s.lower()), 
                                           src_json['subtypes']))]

    if 'rarity' in src_json:
        if src_json['rarity'] in utils.json_rarity_map:
            fields[field_rarity] = [(-1, utils.json_rarity_map[src_json['rarity']])]
        else:
            fields[field_rarity] = [(-1, src_json['rarity'])]
            parsed = False
    else:
        parsed = False

    if 'loyalty' in src_json:
        fields[field_loyalty] = [(-1, utils.to_unary(str(src_json['loyalty'])))]

    p_t = ''
    parsed_pt = True
    if 'power' in src_json:
        p_t = utils.to_ascii(utils.to_unary(src_json['power'])) + '/' # hardcoded
        parsed_pt = False
        if 'toughness' in src_json:
            p_t = p_t + utils.to_ascii(utils.to_unary(src_json['toughness']))
            parsed_pt = True
    elif 'toughness' in src_json:
        p_t = '/' + utils.to_ascii(utils.to_unary(src_json['toughness'])) # hardcoded
        parsed_pt = False
    if p_t:
        fields[field_pt] = [(-1, p_t)]
    parsed = parsed and parsed_pt
        
    # similarly, return the actual Manatext object
    if 'text' in src_json:
        text_val = src_json['text'].lower()
        text_val = transforms.text_pass_1_strip_rt(text_val)
        text_val = transforms.text_pass_2_cardname(text_val, name_orig)
        text_val = transforms.text_pass_3_unary(text_val)
        text_val = transforms.text_pass_4a_dashes(text_val)
        text_val = transforms.text_pass_4b_x(text_val)
        text_val = transforms.text_pass_5_counters(text_val)
        text_val = transforms.text_pass_6_uncast(text_val)
        text_val = transforms.text_pass_7_choice(text_val)
        text_val = transforms.text_pass_8_equip(text_val)
        text_val = transforms.text_pass_9_newlines(text_val)
        text_val = transforms.text_pass_10_symbols(text_val)
        text_val = utils.to_ascii(text_val)
        text_val = text_val.strip()
        mtext = Manatext(text_val, fmt = 'json')
        valid = valid and mtext.valid
        fields[field_text] = [(-1, mtext)]
    
    # we don't need to worry about bsides because we handle that in the constructor
    return parsed, valid and fields_check_valid(fields), fields


def fields_from_format(src_text, fmt_ordered, fmt_labeled, fieldsep):
    parsed = True
    valid = True
    fields = {}

    if fmt_labeled:
        labels = {fmt_labeled[k] : k for k in fmt_labeled}
        field_label_regex = '[' + ''.join(labels.keys()) + ']'
    def addf(fields, fkey, fval):
        # make sure you pass a pair
        if fval and fval[1]:
            if fkey in fields:
                fields[fkey] += [fval]
            else:
                fields[fkey] = [fval]

    textfields = src_text.split(fieldsep)
    idx = 0
    true_idx = 0
    for textfield in textfields:
        # ignore leading or trailing empty fields due to seps
        if textfield == '':
            if true_idx == 0 or true_idx == len(textfields) - 1:
                true_idx += 1
                continue
            # count the field index for other empty fields but don't add them
            else:
                idx += 1
                true_idx += 1
                continue

        lab = None
        if fmt_labeled:
            labs = re.findall(field_label_regex, textfield)
            # use the first label if we saw any at all
            if len(labs) > 0:
                lab = labs[0]
                textfield = textfield.replace(lab, '', 1)
        # try to use the field label if we got one
        if lab and lab in labels:
            fname = labels[lab]
        # fall back to the field order specified
        elif idx < len(fmt_ordered):
            fname = fmt_ordered[idx]
        # we don't know what to do with this field: call it other
        else:
            fname = field_other
            parsed = False
            valid = False

        # specialized handling
        if fname in [field_cost]:
            fval = Manacost(textfield)
            parsed = parsed and fval.parsed
            valid = valid and fval.valid
            addf(fields, fname, (idx, fval))
        elif fname in [field_text]:
            fval = Manatext(textfield)
            valid = valid and fval.valid
            addf(fields, fname, (idx, fval))
        elif fname in [field_supertypes, field_types, field_subtypes]:
            addf(fields, fname, (idx, textfield.split()))
        else:
            addf(fields, fname, (idx, textfield))

        idx += 1
        true_idx += 1
        
    # again, bsides are handled by the constructor
    return parsed, valid and fields_check_valid(fields), fields

# Here's the actual Card class that other files should use.

class Card:
    '''card representation with data'''

    def __init__(self, src, fmt_ordered = fmt_ordered_default, 
                            fmt_labeled = fmt_labeled_default, 
                            fieldsep = utils.fieldsep):
        # source fields, exactly one will be set
        self.json = None
        self.raw = None
        # flags
        self.parsed = True
        self.valid = True # only records broken pt right now (broken as in, no /)
        # default values for all fields
        self.__dict__[field_name] = ''
        self.__dict__[field_rarity] = ''
        self.__dict__[field_cost] = Manacost('')
        self.__dict__[field_supertypes] = []
        self.__dict__[field_types] = []
        self.__dict__[field_subtypes] = []
        self.__dict__[field_loyalty] = ''
        self.__dict__[field_loyalty + '_value'] = None
        self.__dict__[field_pt] = ''
        self.__dict__[field_pt + '_p'] = None
        self.__dict__[field_pt + '_p_value'] = None
        self.__dict__[field_pt + '_t'] = None
        self.__dict__[field_pt + '_t_value'] = None
        self.__dict__[field_text] = Manatext('')
        self.__dict__[field_text + '_lines'] = []
        self.__dict__[field_text + '_words'] = []
        self.__dict__[field_other] = []
        self.bside = None
        # format-independent view of processed input
        self.fields = None # will be reset later

        # looks like a json object
        if isinstance(src, dict):
            if utils.json_field_bside in src:
                self.bside = Card(src[utils.json_field_bside],
                                  fmt_ordered = fmt_ordered,
                                  fmt_labeled = fmt_labeled,
                                  fieldsep = fieldsep)
            p_success, v_success, parsed_fields = fields_from_json(src)
            self.parsed = p_success
            self.valid = v_success
            self.fields = parsed_fields
        # otherwise assume text encoding
        else:
            sides = src.split(utils.bsidesep)
            if len(sides) > 1:
                self.bside = Card(utils.bsidesep.join(sides[1:]), 
                                  fmt_ordered = fmt_ordered,
                                  fmt_labeled = fmt_labeled,
                                  fieldsep = fieldsep)
            p_success, v_success, parsed_fields = fields_from_format(sides[0], fmt_ordered, 
                                                                     fmt_labeled,  fieldsep)
            self.parsed = p_success
            self.valid = v_success
            self.fields = parsed_fields
        # amusingly enough, both encodings allow infinitely deep nesting of bsides...

        # python name hackery
        if self.fields:
            for field in self.fields:
                # look for a specialized set function
                if hasattr(self, '_set_' + field):
                    getattr(self, '_set_' + field)(self.fields[field])
                # otherwise use the default one
                elif field in self.__dict__:
                    self.set_field_default(field, self.fields[field])
                # If we don't recognize the field, fail. This is a totally artificial
                # limitation; if we just used the default handler for the else case,
                # we could set arbitrarily named fields.
                else:
                    raise ValueError('python name mangling failure: unknown field for Card(): ' 
                                     + field)
        else:
            # valid but not parsed indicates that the card was apparently empty
            self.parsed = False

    # These setters are invoked via name mangling, so they have to match 
    # the field names specified above to be used. Otherwise we just
    # always fall back to the (uninteresting) default handler.

    # Also note that all fields come wrapped in pairs, with the first member
    # specifying the index the field was found at when parsing the card. These will
    # all be -1 if the card was parsed from (unordered) json.

    def set_field_default(self, field, values):
        first = True
        for idx, value in values:
            if first:
                first = False
                self.__dict__[field] = value
            else:
                # stick it in other so we'll be know about it when we format the card
                self.valid = False
                self.__dict__[field_other] += [(idx, '<' + field + '> ' + str(value))]

    def _set_loyalty(self, values):
        first = True
        for idx, value in values:
            if first:
                first = False
                self.__dict__[field_loyalty] = value
                try:
                    self.__dict__[field_loyalty + '_value'] = int(value)
                except ValueError:
                    self.__dict__[field_loyalty + '_value'] = None
                    # Technically '*' could still be valid, but it's unlikely...
            else:
                self.valid = False
                self.__dict__[field_other] += [(idx, '<loyalty> ' + str(value))]

    def _set_pt(self, values):
        first = True
        for idx, value in values:
            if first:
                first = False
                self.__dict__[field_pt] = value
                p_t = value.split('/') # hardcoded
                if len(p_t) == 2:
                    self.__dict__[field_pt + '_p'] = p_t[0]
                    try:
                        self.__dict__[field_pt + '_p_value'] = int(p_t[0])
                    except ValueError:
                        self.__dict__[field_pt + '_p_value'] = None
                    self.__dict__[field_pt + '_t'] = p_t[1]
                    try:
                        self.__dict__[field_pt + '_t_value'] = int(p_t[1])
                    except ValueError:
                        self.__dict__[field_pt + '_t_value'] = None
                else:
                    self.valid = False
            else:
                self.valid = False
                self.__dict__[field_other] += [(idx, '<pt> ' + str(value))]
    
    def _set_text(self, values):
        first = True
        for idx, value in values:
            if first:
                first = False
                mtext = value
                self.__dict__[field_text] = mtext
                fulltext = mtext.encode()
                if fulltext:
                    self.__dict__[field_text + '_lines'] = map(Manatext, 
                                                               fulltext.split(utils.newline))
                    self.__dict__[field_text + '_words'] = re.sub(utils.unletters_regex, 
                                                                  ' ', 
                                                                  fulltext).split()
            else:
                self.valid = False
                self.__dict__[field_other] += [(idx, '<text> ' + str(value))]
        
    def _set_other(self, values):
        # just record these, we could do somthing unset valid if we really wanted
        for idx, value in values:
            self.__dict__[field_other] += [(idx, value)]

    # Output functions that produce various formats. encode() is specific to
    # the NN representation, use str() or format() for output intended for human
    # readers.

    def encode(self, fmt_ordered = fmt_ordered_default,
               fmt_labeled = None, fieldsep = utils.fieldsep,
               randomize_fields = False, randomize_mana = False,
               initial_sep = True, final_sep = True):
        outfields = []

        for field in fmt_ordered:
            if field in self.__dict__:
                outfield = self.__dict__[field]
                if outfield:
                    # specialized field handling for the ones that aren't strings (sigh)
                    if isinstance(outfield, list):
                        outfield_str = ' '.join(outfield)
                    elif isinstance(outfield, Manacost):
                        outfield_str = outfield.encode(randomize = randomize_mana)
                    elif isinstance(outfield, Manatext):
                        outfield_str = outfield.encode(randomize = randomize_mana)
                    else:
                        outfield_str = outfield
                else:
                    outfield_str = ''

                if fmt_labeled and field in fmt_labeled:
                        outfield_str = fmt_labeled[field] + outfield_str

                outfields += [outfield_str]

            else:
                raise ValueError('unknown field for Card.encode(): ' + str(field))

        if randomize_fields:
            random.shuffle(outfields)
        if initial_sep:
            outfields = [''] + outfields
        if final_sep:
            outfields = outfields + ['']
        
        outstr = fieldsep.join(outfields)

        if self.bside:
            outstr = (outstr + utils.bsidesep 
                      + self.bside.encode(fmt_ordered = fmt_ordered,
                                          fmt_labeled = fmt_labeled,
                                          fieldsep = fieldsep,
                                          randomize_fields = randomize_fields, 
                                          randomize_mana = randomize_mana,
                                          initial_sep = initial_sep, final_sep = final_sep))

        return outstr

    def format(self, gatherer = False, for_forum = False, for_mse = False):
        outstr = ''
        if gatherer:
            cardname = titlecase(self.__dict__[field_name])
            if not cardname:
                cardname = '_NONAME_'
            if for_forum:
                outstr += '[b]'
            outstr += cardname
            if for_forum:
                outstr += '[/b]'

            outstr += ' ' + self.__dict__[field_cost].format(for_forum = for_forum)

            if self.__dict__[field_rarity]:
                if self.__dict__[field_rarity] in utils.json_rarity_unmap:
                    rarity = utils.json_rarity_unmap[self.__dict__[field_rarity]]
                else:
                    rarity = self.__dict__[field_rarity]
                outstr += ' (' + rarity + ')'

            if not self.parsed:
                outstr += ' _UNPARSED_'
            if not self.valid:
                outstr += ' _INVALID_'
                
            outstr += '\n'

            basetypes = map(str.capitalize, self.__dict__[field_types])
            if len(basetypes) < 1:
                basetypes = ['_NOTYPE_']
            
            outstr += ' '.join(map(str.capitalize, self.__dict__[field_supertypes]) + basetypes)

            if self.__dict__[field_subtypes]:
                outstr += (' ' + utils.dash_marker + ' ' + 
                           ' '.join(self.__dict__[field_subtypes]).title())

            if self.__dict__[field_pt]:
                outstr += ' (' + utils.from_unary(self.__dict__[field_pt]) + ')'

            if self.__dict__[field_loyalty]:
                outstr += ' ((' + utils.from_unary(self.__dict__[field_loyalty]) + '))'

            outstr += '\n'

            if self.__dict__[field_text].text:
                mtext = self.__dict__[field_text].text
                mtext = transforms.text_unpass_1_choice(mtext, delimit = False)
                mtext = transforms.text_unpass_2_counters(mtext)
                mtext = transforms.text_unpass_3_unary(mtext)
                mtext = transforms.text_unpass_4_symbols(mtext, for_forum)
                mtext = sentencecase(mtext)
                mtext = transforms.text_unpass_5_cardname(mtext, cardname)
                mtext = transforms.text_unpass_6_newlines(mtext)
                newtext = Manatext('')
                newtext.text = mtext
                newtext.costs = self.__dict__[field_text].costs
                outstr += newtext.format(for_forum = for_forum)
            
                outstr += '\n'

            if self.__dict__[field_other]:
                if for_forum:
                    outstr += '[i]'
                else:
                    outstr += utils.dash_marker * 2
                    outstr += '\n'
                for idx, value in self.__dict__[field_other]:
                    outstr += '<' + str(idx) + '> ' + str(value)
                    outstr += '\n'
                if for_forum:
                    outstr = outstr[:-1] # hack off the last newline
                    outstr += '[/i]'
                    outstr += '\n'

        elif for_forum:
            cardname = self.__dict__[field_name]
            outstr += cardname
            if self.__dict__[field_rarity]:
                if self.__dict__[field_rarity] in utils.json_rarity_unmap:
                    rarity = utils.json_rarity_unmap[self.__dict__[field_rarity]]
                else:
                    rarity = self.__dict__[field_rarity]
                outstr += ' (' + rarity.lower() + ')'
            if not self.parsed:
                outstr += ' _UNPARSED_'
            if not self.valid:
                outstr += ' _INVALID_'
            outstr += '\n'
            
            outstr += self.__dict__[field_cost].format(for_forum = for_forum)
            outstr += '\n'

            outstr += ' '.join(self.__dict__[field_supertypes] + self.__dict__[field_types])
            if self.__dict__[field_subtypes]:
                outstr += ' ' + utils.dash_marker + ' ' + ' '.join(self.__dict__[field_subtypes])
            outstr += '\n'
            
            if self.__dict__[field_text].text:
                mtext = self.__dict__[field_text].text
                mtext = transforms.text_unpass_1_choice(mtext, delimit = True)
                #mtext = transforms.text_unpass_2_counters(mtext)
                mtext = transforms.text_unpass_3_unary(mtext)
                mtext = transforms.text_unpass_4_symbols(mtext, for_forum)
                #mtext = transforms.text_unpass_5_cardname(mtext, cardname)
                mtext = transforms.text_unpass_6_newlines(mtext)
                newtext = Manatext('')
                newtext.text = mtext
                newtext.costs = self.__dict__[field_text].costs
                outstr += newtext.format(for_forum = for_forum) + '\n'

            if self.__dict__[field_pt]:
                outstr += '(' + utils.from_unary(self.__dict__[field_pt]) + ')'
                outstr += '\n'

            if self.__dict__[field_loyalty]:
                outstr += '((' + utils.from_unary(self.__dict__[field_loyalty]) + '))'
                outstr += '\n'
                
            if self.__dict__[field_other]:
                outstr += utils.dash_marker * 2
                outstr += '\n'
                for idx, value in self.__dict__[field_other]:
                    outstr += '<' + str(idx) + '> ' + str(value)
                    outstr += '\n'


        elif for_mse:
            # need a 'card' string first
            outstr += 'card:\n'
            cardname = titlecase(self.__dict__[field_name])
            outstr += '\tname: ' + cardname + '\n'
            if self.__dict__[field_rarity]:
                if self.__dict__[field_rarity] in utils.json_rarity_unmap:
                    rarity = utils.json_rarity_unmap[self.__dict__[field_rarity]]
                else:
                    rarity = self.__dict__[field_rarity]
                outstr += '\trarity: ' + rarity.lower() + '\n'
            #if not self.parsed:
            #    outstr += ' _UNPARSED_'
            #if not self.valid:
            #    outstr += ' _INVALID_'
            
            if "land" not in self.__dict__[field_types]:            
                outstr += '\tcasting cost: ' + self.__dict__[field_cost].format(for_forum = for_forum).replace('{','').replace('}','')
                outstr += '\n'

            outstr += '\tsuper type: ' + ' '.join(self.__dict__[field_supertypes] + self.__dict__[field_types]).title() + '\n'
            #outstr += 'sub type: ' + ' '.join(self.__dict__[field_types])
            if self.__dict__[field_subtypes]:
                outstr += '\tsub type: ' + ' '.join(self.__dict__[field_subtypes]).title()
                outstr += '\n'
            
            if self.__dict__[field_text].text:
                mtext = self.__dict__[field_text].text
                mtext = transforms.text_unpass_1_choice(mtext, delimit = False)
                mtext = transforms.text_unpass_2_counters(mtext)
                mtext = transforms.text_unpass_3_unary(mtext)
                mtext = transforms.text_unpass_4_symbols(mtext, for_forum)
                mtext = transforms.text_unpass_5_cardname(mtext, cardname)
                mtext = transforms.text_unpass_6_newlines(mtext)
                newtext = Manatext('')
                newtext.text = mtext
                newtext.costs = self.__dict__[field_text].costs
                newtext = newtext.format(for_forum = for_forum)
                newtext = newtext.replace(utils.this_marker, cardname) # first let's put the cardname where all the @s are.
                newtext = newtext.replace(utils.counter_rename + ".", "countered.") # then replace any 'uncast' at the end of a sentence with 'countered'.
                newtext = newtext.replace(utils.dash_marker, "—") # also replace the ~ with a — for choices.
                newtext = newtext.replace(utils.counter_rename, "counter") # then replace all the mid-sentence 'uncast' with 'counter'.
                newtext = newtext.replace('{','<sym-auto>').replace('}','</sym-auto>') # now we encase mana/tap symbols with the correct tags for mse.
                linecount = newtext.count('\n') + 1 # adding 1 because no newlines means 1 line, 1 newline means 2 lines etc.

                newtext = uppercaseNewLineAndFullstop(newtext) # make all the things uppercase!

                # done after uppercasing everything because string[i] == • doesn't work apparently.
                newtext = newtext.replace(utils.bullet_marker, "•") # replace the = with a •. 

                newlineIndices = [0] # also need to keep track of pure newlines (for planeswalkers).
                for i in range (len(newtext)):
                    if  newtext[i] == '\n':
                        newlineIndices.append(i + 1)

                # need to do Special Things if it's a planeswalker.
                if "planeswalker" in str(self.__dict__[field_types]): # for some reason this is in types, not supertypes...
                    outstr += '\tstylesheet: m15-planeswalker\n' # set the proper card style for a 3-line walker.

                    # set up the loyalty cost fields using regex to find how many there are.
                    i = 0
                    for costs in re.findall('[-+]\d?\d: ', newtext): # regex handles 2-figure loyalty costs.
                        i += 1
                        outstr += '\tloyalty cost ' + str(i) + ': ' + costs + '\n'
                    # sub out the loyalty costs.
                    newtext = re.sub('[-+]\d?\d: ', '', newtext)

                    newtext = uppercaseNewLineAndFullstop(newtext) # we need to uppercase again; previous uppercase call didn't work due to loyalty costs being there.

                    if self.__dict__[field_loyalty]:
                        outstr += '\tloyalty: ' + utils.from_unary(self.__dict__[field_loyalty]) + '\n'

                # have to do special snowflake stuff for rule text with more than 1 line. 2 or more lines need to be double-indented...                
                if linecount == 1:
                    outstr += '\trule text: ' + newtext + '\n'
                elif linecount > 1:
                    newtext = newtext.replace('\n','\n\t\t')
                    outstr += '\trule text:\n\t\t' + newtext + '\n'

                # also uncast still exists at this point? weird. should be 'unpassed' apparently. until then, did a manual replace.

            if self.__dict__[field_pt]:
                ptstring = utils.from_unary(self.__dict__[field_pt]).split('/')
                if (len(ptstring) > 1): #really don't want to be accessing anything nonexistent.
                    outstr += '\tpower: ' + ptstring[0] + '\n'
                    outstr += '\ttoughness: ' + ptstring[1] + '\n'
                #outstr += '\n'

            # now append all the other useless fields that the setfile expects.
            outstr += '\thas styling: false\n\tnotes:\n\ttime created:2015-07-20 22:53:07\n\ttime modified:2015-07-20 22:53:08\n\textra data:\n\timage:\n\tcard code text:\n\tcopyright:\n\timage 2:\n\tcopyright 2: '

            #print outstr

        if self.bside and not for_mse:
            outstr += utils.dash_marker * 8 + '\n'
            outstr += self.bside.format(gatherer = gatherer, for_forum = for_forum)

        return outstr
    
    def vectorize(self):
        ld = '('
        rd = ')'
        outstr = ''

        if self.__dict__[field_rarity]:
            outstr += ld + self.__dict__[field_rarity] + rd + ' '

        coststr = self.__dict__[field_cost].vectorize(delimit = True)
        if coststr:
            outstr += coststr + ' '

        typestr = ' '.join(map(lambda s: '(' + s + ')',
                               self.__dict__[field_supertypes] + self.__dict__[field_types]))
        if typestr:
            outstr += typestr + ' '

        if self.__dict__[field_subtypes]:
            outstr += ' '.join(self.__dict__[field_subtypes]) + ' '

        if self.__dict__[field_pt]:
            outstr += ' '.join(map(lambda s: '(' + s + ')',
                                   self.__dict__[field_pt].replace('/', '/ /').split()))
            outstr += ' '
        
        if self.__dict__[field_loyalty]:
            outstr += '((' + self.__dict__[field_loyalty] + ')) '
            
        outstr += self.__dict__[field_text].vectorize()

        if self.bside:
            outstr = '_ASIDE_ ' + outstr + '\n\n_BSIDE_ ' + self.bside.vectorize()

        return outstr
            

        
