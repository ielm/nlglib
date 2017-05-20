""" Data structures used by other packages. """

import inspect
import importlib
import json
import logging
import os

from copy import deepcopy
from os.path import join, dirname, relpath
from urllib.parse import quote_plus

from nlglib.utils import flatten

logger = logging.getLogger(__name__)


class Document:
    """Document represents a container holding information about a document.

    This includes the document title and a list of sections.

    """

    def __init__(self, title, *sections):
        """ Create a new Document instance with given title and with zero or more sections. """
        self.title = title if isinstance(title, Message) else Message('', title)
        self.sections = [s if isinstance(s, Section) else Section('', s)
                         for s in sections if s is not None]

    def __repr__(self):
        return '<Document: ({})'.format(self.title)

    def __str__(self):
        return str(self.title) + '\n' + '\n\n'.join([str(s) for s in self.sections])

    def __eq__(self, other):
        return (isinstance(other, Document) and
                self.title == other.title and
                self.sections == other.sections)

    def __hash__(self):
        return hash(str(self))

    def constituents(self):
        """ Return a generator to iterate through the elements. """
        yield self.title
        for x in self.sections:
            yield from x.constituents()

    def to_xml(self, offset='', indent='  '):
        """Return an XML representation of the document indented by initial ``offset``"
        :param offset: the initial offset
        :param indent: the indent for nested elements.
        """
        result = offset + '<document>\n'
        result += offset + indent + '<title>\n'
        result += self.title.to_xml(offset + 2 * indent)
        result += offset + indent + '</title>\n'
        result += offset + indent + '<sections>\n'
        for s in self.sections:
            result += s.to_xml(offset=(offset + indent))
        result += offset + indent + '</sections>\n'
        result += offset + '</document>\n'
        return result


class Section:
    """Section is a container holding information about a section of a document.

     A section has a title and a list of ``Paragraph``s or ``Section``s.

    """

    def __init__(self, title, *paragraphs):
        """ Create a new section with given title and zero or more paragraphs. """
        self.title = title if isinstance(title, Message) else Message('', title)
        self.content = [p if isinstance(p, (Paragraph, Section)) else Paragraph(p)
                        for p in paragraphs if p is not None]

    def __repr__(self):
        return '<Section: {}>'.format(self.title)

    def __str__(self):
        return str(self.title) + '\n' + '\n'.join([str(p) for p in self.content])

    def __eq__(self, other):
        return (isinstance(other, Section) and
                self.title == other.title and
                self.content == other.paragraphs)

    def __hash__(self):
        return hash(str(self))

    def constituents(self):
        """ Return a generator to iterate through the elements. """
        yield self.title
        for x in self.content:
            yield from x.constituents()

    def to_xml(self, offset='', indent='  '):
        """Return an XML representation of the section indented by initial ``offset``"
        :param offset: the initial offset
        :param indent: the indent for nested elements.
        """
        result = offset + '<section>\n'
        result += offset + indent + '<title>\n'
        result += self.title.to_xml(offset + 2 * indent)
        result += offset + indent + '</title>\n'
        result += offset + indent + '<paragraphs>\n'
        for p in self.content:
            result += p.to_xml(offset=(offset + 2 * indent))
        result += offset + indent + '</paragraphs>\n'
        result += offset + '</section>\n'
        return result


class Paragraph:
    """Paragraph represents a container holding information about a paragraph of a document.

     Paragraph is a list of ``Message``s.

    """

    def __init__(self, *messages):
        """ Create a new Paragraph with zero or more messages. """
        self.messages = [m if isinstance(m, Message) else Message('Leaf', m) for m in flatten(messages)]

    def __repr__(self):
        return '<Paragraph {}>'.format(str(self.messages)[:25])

    def __str__(self):
        descr = ('\t' +
                 '; '.join([str(m) for m in self.messages if m is not None]))
        return descr

    def __eq__(self, other):
        return (isinstance(other, Paragraph) and
                self.messages == other.messages)

    def constituents(self):
        """ Return a generator to iterate through the elements. """
        for x in self.messages: yield from x.constituents()

    def to_xml(self, offset='', indent='  '):
        """Return an XML representation of the paragraph indented by initial ``offset``"
        :param offset: the initial offset
        :param indent: the indent for nested elements.
        """
        result = offset + '<paragraph>\n'
        result += offset + indent + '<messages>\n'
        for m in self.messages:
            result += m.to_xml(offset=(offset + indent))
        result += offset + indent + '</messages>\n'
        result += offset + '</paragraph>\n'
        return result


class Message:
    """ A representation of a message (usually a sentence).
        A message has a nucleus and zero or more satellites joined
        by an RST (Rhetorical Structure Theory) relation.

    """

    def __init__(self, rel, nucleus, *satellites, features=None):
        """ Create a new Message with given relation between
        the nucleus and zero or more satellites.

        """
        # FIXME: messages should have only one satellite and 1+ nuclei
        self.rst = rel
        self.nucleus = nucleus
        self.satellites = [s for s in satellites if s is not None]
        self.marker = ''
        self.features = features or {}

    def __repr__(self):
        descr = ' '.join([repr(x) for x in
                          ([self.nucleus] + self.satellites) if x is not None])
        if descr == '': descr = '_empty_'
        return 'Message (%s): %s' % (self.rst, descr.strip())

    def __str__(self):
        descr = ' '.join([str(x) for x in
                          ([self.nucleus] + self.satellites) if x is not None])
        return descr.strip() if descr is not None else ''

    def __eq__(self, other):
        return (isinstance(other, Message) and
                self.rst == other.rst and
                self.nucleus == other.nucleus and
                self.satellites == other.satellites)

    def constituents(self):
        """ Return a generator to iterate through the elements. """
        if self.nucleus:
            if hasattr(self.nucleus, 'constituents'):
                yield from self.nucleus.constituents()
            else:
                yield self.nucleus
        for x in self.satellites:
            if hasattr(x, 'constituents'):
                yield from x.constituents()
            else:
                yield x

    def del_feature(self, feat, val=None):
        """ Delete a feature, if the element has it else do nothing.
        If val is None, delete whathever value is assigned to the feature.
        Otherwise only delete the feature if it has matching value.

        """
        if feat in self.features:
            if val is not None:
                del self.features[feat]
            elif val == self.features[feat]:
                del self.features[feat]

    def addfeatures(self, features):
        """ Add the given features (dict) to the existing features. """
        for k, v in features.items():
            self.features[k] = v

    def to_xml(self, offset='', indent='  '):
        """Return an XML representation of the paragraph indented by initial ``offset``"
        :param offset: the initial offset
        :param indent: the indent for nested elements.
        """
        result = offset + '<message type="{}">\n'.format(self.rst)
        result += offset + indent + '<marker>{}</marker>\n'.format(self.marker)
        result += offset + indent + '<nucleus>\n'
        result += self.nucleus.to_xml(offset=(offset + 2 * indent))
        result += offset + indent + '</nucleus>\n'
        for s in self.satellites:
            result += offset + indent + '<satellite>\n'
            result += s.to_xml(offset=(offset + 2 * indent))
            result += offset + indent + '</satellite>\n'
        result += offset + '</message>\n'
        return result


class RhetRep:
    """ A representation of a rhetorical structure.
    The data structure is from RAGS (Mellish et. al. 2006) and it represents
    an element in the rhetorical structure of the document. Each element has
    a nucleus, a satellite and a relation name. Some relations allow multiple
    nuclei instead of a satellite (e.g., lists).

    Rhetorical structure is a tree. The children can be either RhetReps
    or MsgSpecs.

    """

    def __init__(self, relation, *nuclei, satellite=None, marker=None):
        self.relation = relation
        self.nucleus = list(nuclei)
        self.satellite = satellite
        self.is_multinuclear = (len(nuclei) > 1)
        self.marker = marker

    def to_xml(self, lvl=0, indent='  '):
        spaces = indent * lvl
        data = spaces + '<rhetrep name="' + str(self.relation) + '">\n'
        data += indent + spaces + '<marker>' + (self.marker or '') + '</marker>\n'
        if self.is_multinuclear:
            data += ''.join([e.to_xml(lvl + 1) for e in self.nucleus])
        else:
            data += ''.join([e.to_xml(lvl + 1) for e in (self.nucleus, self.satellite)])
        data += spaces + '</rhetrep>\n'
        return data

    def to_str(self):
        pass


class SemRep:
    def __init__(self, clause, **features):
        self.clause = clause
        self.features = features or dict()

    def to_xml(self, lvl=0, indent='  '):
        spaces = indent * lvl
        data = spaces + '<semrep>\n'
        data += spaces + indent + str(self.clause) + '\n'
        data += spaces + '</semrep>\n'
        return data


class MsgSpec:
    """ MsgSpec specifies an interface for various message specifications.
    Because the specifications are domain dependent, this is just a convenience
    interface that allows the rest of the library to operate on the messages.

    The name of the message is used during lexicalisation where the name is
    looked up in an ontology to find corresponding syntactic frame. To populate
    the frame, the lexicaliser finds all variables and uses their names
    as a key to look up the values in the corresponding message. For example,
    if the syntactic structure in the domain ontology specifies a variable
    named 'foo', the lexicaliser will call msg.value_for('foo'), which
    in turn calls self.foo(). This should return the value for the key 'foo'.

    """

    def __init__(self, name, features=None):
        self.name = name
        self.features = features or {}
        self._visitor_name = 'visit_msg_spec'

    def __repr__(self):
        return 'MsgSpec({0}, {1})'.format(self.name, self.features)

    def __str__(self):
        return str(self.name)

    def __eq__(self, other):
        return (isinstance(other, type(self)) and
                self.name == other.name)

    def value_for(self, data_member):
        """ Return a value for an argument using introspection. """
        if not hasattr(self, data_member):
            raise ValueError('Error: cannot find value for key: %s' %
                             data_member)
        m = getattr(self, data_member)
        if not hasattr(m, '__call__'):
            raise ValueError('Error: cannot call the method "%s"' %
                             data_member)
        return m()

    def accept(self, visitor, element='Element'):
        """Implementation of the Visitor pattern."""
        if self._visitor_name == None:
            raise ValueError('Error: visit method of uninitialized visitor '
                             'called!')
        # get the appropriate method of the visitor instance
        m = getattr(visitor, self._visitor_name)
        # ensure that the method is callable
        if not hasattr(m, '__call__'):
            raise ValueError('Error: cannot call undefined method: %s on '
                             'visitor' % self._visitor_name)
        sig = inspect.signature(m)
        # and finally call the callback
        if len(sig.parameters) == 1:
            return m(self)
        if len(sig.parameters) == 2:
            return m(self, element)

    def constituents(self):
        return [self]

    @classmethod
    def instantiate(Klass, data):
        return None

    def del_feature(self, feat, val=None):
        """ Delete a feature, if the element has it else do nothing.
        If val is None, delete whathever value is assigned to the feature.
        Otherwise only delete the feature if it has matching value.

        """
        if feat in self.features:
            if val is not None:
                del self.features[feat]
            elif val == self.features[feat]:
                del self.features[feat]

    def addfeatures(self, features):
        """ Add the given features (dict) to the existing features. """
        for k, v in features.items():
            self.features[k] = v


class StringMsgSpec(MsgSpec):
    """ Use this as a simple message that contains canned text. """

    def __init__(self, text):
        super().__init__('string_message')
        self.text = text

    def __str__(self):
        return str(self.text)

    def value_for(self, _):
        return String(self.text)

    def to_xml(self, offset='', indent='  '):
        """Return an XML representation of the paragraph indented by initial ``offset``"
        :param offset: the initial offset
        :param indent: the indent for nested elements.
        """
        result = offset + '<msgspec template_name="{}">\n'.format(self.name)
        result += offset + indent + '<text>{}</text>\n'.format(self.text)
        result += offset + '</msgspec>\n'
        return result


class DiscourseContext:
    """ A class that captures the discourse referents and history. """

    def __init__(self):
        self.referents = []
        self.history = []
        self.referent_info = {}


class OperatorContext:
    """ A class that captures the operators in a logical formula. """

    def __init__(self):
        self.variables = []
        self.symbols = []
        self.negations = 0


###############################################################################
#                                                                              #
#                              microplanning                                   #
#                                                                              #
###############################################################################


class ElemntCoder(json.JSONEncoder):
    @staticmethod
    def to_json(python_object):
        if isinstance(python_object, Element):
            return {'__class__': str(type(python_object)),
                    '__value__': python_object.__dict__}
        raise TypeError(repr(python_object) + ' is not JSON serializable')

    @staticmethod
    def from_json(json_object):
        if '__class__' in json_object:
            if json_object['__class__'] == "<class 'nlglib.structures.Element'>":
                return Element.from_dict(json_object['__value__'])
            if json_object['__class__'] == "<class 'nlglib.structures.String'>":
                return String.from_dict(json_object['__value__'])
            if json_object['__class__'] == "<class 'nlglib.structures.Word'>":
                return Word.from_dict(json_object['__value__'])
            if json_object['__class__'] == "<class 'nlglib.structures.Var'>":
                return Var.from_dict(json_object['__value__'])
            if json_object['__class__'] == "<class 'nlglib.structures.Phrase'>":
                return Phrase.from_dict(json_object['__value__'])
            if json_object['__class__'] == "<class 'nlglib.structures.Clause'>":
                return Clause.from_dict(json_object['__value__'])
            if json_object['__class__'] == "<class 'nlglib.structures.NounPhrase'>":
                return NounPhrase.from_dict(json_object['__value__'])
            if json_object['__class__'] == "<class 'nlglib.structures.VerbPhrase'>":
                return VerbPhrase.from_dict(json_object['__value__'])
            if json_object['__class__'] == "<class 'nlglib.structures.PrepositionalPhrase'>":
                return PrepositionalPhrase.from_dict(json_object['__value__'])
            if json_object['__class__'] == "<class 'nlglib.structures.AdjectivePhrase'>":
                return AdjectivePhrase.from_dict(json_object['__value__'])
            if json_object['__class__'] == "<class 'nlglib.structures.AdverbPhrase'>":
                return AdverbPhrase.from_dict(json_object['__value__'])
            if json_object['__class__'] == "<class 'nlglib.structures.Coordination'>":
                return Coordination.from_dict(json_object['__value__'])

        return json_object


# types of clauses:
ELEMENT = 0  # abstract
STRING = 1
WORD = 2
VAR = 3
CLAUSE = 4

COORDINATION = 5
SUBORDINATION = 6

PHRASE = 10  # abstract
NOUN_PHRASE = 11
VERB_PHRASE = 12
PREPOSITIONAL_PHRASE = 13
ADJECTIVE_PHRASE = 14
ADVERB_PHRASE = 15

# visitor names
VisitorNames = {
    ELEMENT: 'visit_element',
    STRING: 'visit_string',
    WORD: 'visit_word',
    VAR: 'visit_var',
    CLAUSE: 'visit_clause',

    COORDINATION: 'visit_coordination',
    SUBORDINATION: 'visit_subordination',

    PHRASE: 'visit_phrase',
    NOUN_PHRASE: 'visit_np',
    VERB_PHRASE: 'visit_vp',
    PREPOSITIONAL_PHRASE: 'visit_pp',
    ADJECTIVE_PHRASE: 'visit_adjp',
    ADVERB_PHRASE: 'visit_advp',
}


def is_element_t(o):
    """ An object is an element if it has attr _type and one of the types. """
    if not hasattr(o, '_type'):
        return False
    else:
        return o._type in VisitorNames


def is_phrase_t(o):
    """ An object is a phrase type if it is a phrase or a coordination of
    phrases.

    """
    return (is_element_t(o) and
            (o._type in {PHRASE, NounPhrase, VerbPhrase, PrepositionalPhrase, ADJECTIVE_PHRASE, ADVERB_PHRASE} or
             (o._type == COORDINATION and
              (o.coords == [] or is_phrase_t(o.coords[0])))))


def is_clause_t(o):
    """ An object is a clause type if it is a clause, subordination or
    a coordination of clauses.

    """
    return (is_element_t(o) and
            ((o._type in {CLAUSE, SUBORDINATION}) or
             (o._type == COORDINATION and any(map(is_clause_t, o.coords)))))


def is_adj_mod_t(o):
    """Return True if `o` is adjective modifier (adj or AdjP)"""
    from nlglib import lexicon
    return (isinstance(o, AdjectivePhrase) or
            isinstance(o, Word) and o.pos == lexicon.POS_ADJECTIVE or
            isinstance(o, Coordination) and is_adj_mod_t(o.coords[0]))


def is_adv_mod_t(o):
    """Return True if `o` is adverb modifier (adv or AdvP)"""
    from nlglib import lexicon
    return (isinstance(o, AdverbPhrase) or
            isinstance(o, Word) and o.pos == lexicon.POS_ADVERB or
            isinstance(o, Coordination) and is_adv_mod_t(o.coords[0]))


def is_noun_t(o):
    """Return True if `o` is adverb modifier (adv or AdvP)"""
    from nlglib import lexicon
    return (isinstance(o, NounPhrase) or
            isinstance(o, Word) and o.pos == lexicon.POS_NOUN or
            isinstance(o, Coordination) and is_noun_t(o.coords[0]))


def str_to_elt(*params):
    """ Check that all params are Elements and convert
    and any strings to String.

    """
    fn = lambda x: String(x) if isinstance(x, str) else x
    return list(map(fn, params))


class FeatureModulesLoader(type):

    """Metaclass injecting the feature module property onto a class."""

    def __new__(cls, clsname, bases, dct):
        features = {}
        feature_pkg_path = relpath(
            join(dirname(__file__), '..', 'lexicon', 'feature'))
        for dirpath, _, filenames in os.walk(feature_pkg_path):
            pkg_root = dirpath.replace('/', '.')
            for filename in filenames:
                if not filename.endswith('.py'):
                    continue
                pkg_path = pkg_root + '.' + filename.replace('.py', '')
                if pkg_path.startswith('.'):  # no relative imports please
                    _, root, child = pkg_path.rpartition('pynlg')
                    pkg_path = root + child
                mod = importlib.import_module(pkg_path)
                modfeatures = [c for c in dir(mod) if c.isupper()]
                for feat in modfeatures:
                    features[feat] = getattr(mod, feat)

        dct['_feature_constants'] = features

        return super(FeatureModulesLoader, cls).__new__(
            cls, clsname, bases, dct)


class Element(object, metaclass=FeatureModulesLoader):
    """ A base class representing an NLG element.
        Aside for providing a base class for othe kinds of NLG elements,
        the class also implements basic functionality for elements.

    """

    def __init__(self, type=ELEMENT, features=None, parent=None):
        if features and not isinstance(features, dict):
            raise ValueError('Features have to be a dict instance.')
        self.id = 0  # this is useful for replacing elements
        self._type = type
        self._visitor_name = VisitorNames[type]
        self.features = deepcopy(features) if features else {}
        self.hash = -1
        self.parent = parent

    def __bool__(self):
        """ Because Element is abstract, it will evaluate to false. """
        return False

    def __eq__(self, other):
        if not is_element_t(other): return False
        if not self._type is other._type: return False
        return (self.id == other.id and
                self.features == other.features)

    def __hash__(self):
        if self.hash == -1:
            self.hash = (hash(self.id) ^ hash(tuple(['k:v'.format(k, v)
                                                     for k, v in self.features.items()])))
        return self.hash

    @classmethod
    def from_dict(Cls, dct):
        o = Cls()
        o.__dict__ = dct
        return o

    def to_JSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, indent=4)

    def __repr__(self):
        from .microplanning import ReprVisitor
        v = ReprVisitor()
        self.accept(v)
        return str(v)

    def __str__(self):
        from .microplanning import StrVisitor
        v = StrVisitor()
        self.accept(v)
        return str(v)

    # feature-related methods
    def __contains__(self, feature_name):
        """Check if the argument feature name is contained in the element."""
        return feature_name in self.features

    def __setitem__(self, feature_name, feature_value):
        """Set the feature name/value in the element feature dict."""
        self.features[feature_name] = feature_value

    def __getitem__(self, feature_name):
        """Return the value associated with the feature name, from the
        element feature dict.

        If the feature name is not found in the feature dict, return None.

        """
        return self.features.get(feature_name)

    def __delitem__(self, feature_name):
        """Remove the argument feature name and its associated value from
        the element feature dict.

        If the feature name was not initially present in the feature dict,
        a KeyError will be raised.

        """
        if feature_name in self.features:
            del self.features[feature_name]

    def __getattr__(self, name):
        """When a undefined attribute name is accessed, try to return
        self.features[name] if it exists.

        If name is not in self.features, but name.upper() is defined as
        a feature constant, don't raise an AttribueError. Instead, try
        to return the feature value associated with the feature constant
        value.

        This allows us to have a more consistant API when
        dealing with NLGElement and instances of sublclasses.

        If no such match is found, raise an AttributeError.

        Example:
        >>> elt = NLGElement(features={'plural': 'plop', 'infl': ['lala']})
        >>> elt.plural
        'plop'  # because 'plural' is in features
        >>> elt.infl
        ['lala']  # because 'infl' is in features
        >>> elt.inflections
        ['lala']  # because INFLECTIONS='infl' is defined as a feature constant
                # constant, and elt.features['infl'] = ['lala']

        """
        n = name.upper()
        flag = 'features' in self.__dict__
        if not flag:
            print('features: {}'.format(flag))
            print(self.__class__)
            raise Exception('flag!')
        if name in self.features:
            return self.features[name]
        elif n in self._feature_constants:
            new_name = self._feature_constants[n]
            return self.features.get(new_name)
        raise AttributeError(name)

    def __deepcopy__(self, memodict={}):
        copyobj = self.__class__(self._type, self.features, self.parent)
        copyobj.id = self.id
        copyobj.hash = self.hash
        return copyobj

    def accept(self, visitor, element='Element'):
        """Implementation of the Visitor pattern."""
        if self._visitor_name == None:
            raise ValueError('Error: visit method of uninitialized visitor '
                             'called!')
        # get the appropriate method of the visitor instance
        m = getattr(visitor, self._visitor_name)
        # ensure that the method is callable
        if not hasattr(m, '__call__'):
            raise ValueError('Error: cannot call undefined method: %s on '
                             'visitor' % self._visitor_name)
        sig = inspect.signature(m)
        # and finally call the callback
        if len(sig.parameters) == 1:
            return m(self)
        if len(sig.parameters) == 2:
            return m(self, element)

    def features_to_xml_attributes(self):
        features = ""
        for (k, v) in self.features.items():
            features += '%s="%s" ' % (quote_plus(str(k)), quote_plus(str(v)))
        features = features.strip()
        if features != '':
            return ' ' + features
        return ''

    def set_feature(self, feature, value):
        """ Add a feature to the feature set.
        If the feature exists, overwrite the old value.

        """
        self.features[feature] = value

    def has_feature(self, feature, value=None):
        """ Return True if the element has the given feature.
        If a value is given, return true if the feature matches the value,
        otherwise return true if the element has some value for the feature.

        """
        if feature in self.features:
            if value is None: return True
            return value == self.features[feature]
        return False

    def get_feature(self, feature):
        """ Return value for given feature or raise KeyError. """
        return self.features[feature]

    def feature(self, feat):
        """ Return value for given feature or None. """
        if feat in self.features:
            return self.features[feat]
        else:
            return None

    def del_feature(self, feat, val=None):
        """ Delete a feature, if the element has it else do nothing.
        If val is None, delete whathever value is assigned to the feature.
        Otherwise only delete the feature if it has matching value.

        """
        if feat in self.features:
            if val is not None:
                del self.features[feat]
            elif val == self.features[feat]:
                del self.features[feat]

    def addfeatures(self, features):
        """ Add the given features (dict) to the existing features. """
        for k, v in features.items():
            self.features[k] = v

    def constituents(self):
        """ Return a generator representing constituents of an element. """
        return []

    def arguments(self):
        """ Return any arguments (vars) from the elemen as a generator.

        """
        return list(filter(lambda x: isinstance(x, Var),
                           self.constituents()))

    def replace(self, one, another):
        """ Replace first occurance of one with another.
        Return True if successful.

        """
        return False  # basic implementation does nothing

    def replace_argument(self, arg_id, repl):
        """ Replace an argument with given id by repl if such argumen exists."""
        for a in self.arguments():
            if a.id == arg_id:
                return self.replace(a, repl)
        return False

    def replace_arguments(self, *args, **kwargs):
        """ Replace arguments with ids in the kwargs by the corresponding
        values.
        Replacements can be passed as a single dictionary or a kwarg list
        (e.g., arg1=x, arg2=y, ...)

        """
        # FIXME: this does not look correct...
        if len(args) > 1:
            raise ValueError('too many parameters')
        elif len(args) > 0:
            for k, v in args[0]:
                self.replace_argument(k, v)
        else:
            for k, v in kwargs.items():
                self.replace_argument(k, v)

    @property
    def string(self):
        """Return the string inside the value. """
        return None

    def _add_to_list(self, lst, *mods, pos=None):
        """ Add modifiers to the given list. Convert any strings to String. """
        if pos is None:
            for mod in mods:
                mod.parent = self
                lst.append(mod)
        else:
            for mod in mods:
                mod.parent = self
                lst.insert(pos, mod)

    @staticmethod
    def _del_from_list(lst, *mods):
        """ Delete elements from a list. Convert any strings to String. """
        for p in str_to_elt(*mods):
            if p in lst: lst.remove(p)


class String(Element):
    """ String is a basic element representing canned text. """

    def __init__(self, val='', features=None, parent=None):
        super().__init__(STRING, features, parent)
        self.value = val

    def __bool__(self):
        """ Return True if the string is non-empty. """
        return len(self.value) > 0

    def __eq__(self, other):
        if (not isinstance(other, String)):
            return False
        return (self.value == other.value and
                super().__eq__(other))

    def __hash__(self):
        if self.hash == -1:
            self.hash = (11 * super().__hash__()) ^ hash(self.value)
        return self.hash

    def __deepcopy__(self, memodict={}):
        copyobj = self.__class__(self.value, self.features, self.parent)
        copyobj.id = self.id
        copyobj.hash = self.hash
        return copyobj

    def constituents(self):
        return [self]

    @property
    def string(self):
        """Return the string inside the value. """
        return self.value


class Word(Element):
    """ Word represents word and its corresponding POS (Part-of-Speech) tag. """

    def __init__(self, word, pos='ANY', features=None, base=None, parent=None):
        super().__init__(WORD, features, parent)
        self.word = word
        self.pos = pos
        self.base = base or word
        self.do_inflection = False
        self.set_feature('cat', pos)

    def __bool__(self):
        """ Return True """
        return True

    def __eq__(self, other):
        if (not isinstance(other, Word)):
            return False
        return (self.word == other.word and
                self.pos == other.pos and
                super().__eq__(other))

    def __hash__(self):
        if self.hash == -1:
            self.hash = ((11 * super().__hash__()) ^
                         (hash(self.pos) ^ hash(self.word)))
        return self.hash

    def __deepcopy__(self, memodict={}):
        copyobj = self.__class__(self.word, self.pos,
                                 self.features, self.base, self.parent)
        copyobj.id = self.id
        copyobj.hash = self.hash
        return copyobj

    def constituents(self):
        return [self]

    @property
    def string(self):
        """Return the word. """
        return self.word


class Var(Element):
    """ An element used as a place-holder in a sentence. The purpose of this
        element is to make replacing arguments easier. For example, in a plan
        one might want to replace arguments of an action with the instantiated
        objects
        E.g.,   move (x, a, b) -->
                move Var(x) from Var(a) to Var(b) -->
                move (the block) from (the table) to (the green block)

    """

    def __init__(self, id=None, obj=None, features=None, parent=None):
        super().__init__(VAR, features, parent)
        self.id = id
        self.value = None
        self.set_value(obj)

    def __bool__(self):
        """ Return True """
        return True

    def __eq__(self, other):
        if not isinstance(other, Var):
            return False
        else:
            return (self.id == other.id and
                    self.value == other.value and
                    super().__eq__(other))

    def __hash__(self):
        if self.hash == -1:
            self.hash = ((11 * super().__hash__()) ^
                         (hash(self.id) & hash(self.value)))
        return self.hash

    def __deepcopy__(self, memodict={}):
        copyobj = self.__class__(self.id, self.value, features=self.features, parent=self.parent)
        copyobj.id = self.id
        copyobj.hash = self.hash
        return copyobj

    def constituents(self):
        return [self]

    def set_value(self, val):
        if val is None: val = Word(str(self.id), 'NOUN')
        self.value = String(val) if isinstance(val, str) else val

    @property
    def string(self):
        """Return the string inside the value. """
        if self.value:
            return self.value.string


class Coordination(Element):
    """ Coordinated clause with a conjunction. """

    def __init__(self, *coords, conj='and', features=None, parent=None, **kwargs):
        super().__init__(COORDINATION, features, parent)
        self.coords = list()
        self.add_coordinate(*coords)
        self.set_feature('conj', conj)
        self.conj = conj
        self.pre_modifiers = list()
        self.complements = list()
        self.post_modifiers = list()
        # see if anything was passed from above...
        if 'pre_modifiers' in kwargs:
            self.pre_modifiers = str_to_elt(*kwargs['pre_modifiers'])
        if 'complements' in kwargs:
            self.complements = str_to_elt(*kwargs['complements'])
        if 'post_modifiers' in kwargs:
            self.post_modifiers = str_to_elt(*kwargs['post_modifiers'])

    def __bool__(self):
        """ Return True """
        return True

    def __eq__(self, other):
        if (not isinstance(other, Coordination)):
            return False
        else:
            return (self.coords == other.coords and
                    self.conj == other.conj and
                    super().__eq__(other))

    def __hash__(self):
        assert False, 'Coordination Element is not hashable'

    def __deepcopy__(self, memodict={}):
        copyobj = self.__class__(conj=self.conj, features=self.features, parent=self.parent)
        copyobj.coords = deepcopy(self.coords)
        copyobj.id = self.id
        return copyobj

    def add_front_modifier(self, *mods, pos=0):
        """ Add front modifiers to the first element. """
        # promote the element to a phrase
        if not is_phrase_t(self.coords[0]):
            self.coords[0] = NounPhrase(self.coords[0])
        self.coords[0].add_front_modifier(*mods, pos=pos)

    def add_pre_modifier(self, *mods, pos=0):
        """ Add pre-modifiers to the first element. """
        # promote the element to a phrase
        if not is_phrase_t(self.coords[0]):
            self.coords[0] = NounPhrase(self.coords[0])
        self.coords[0].add_pre_modifier(*mods, pos=pos)

    def add_complement(self, *mods, pos=None):
        """ Add complements to the last element. """
        # promote the element to a phrase
        if not is_phrase_t(self.coords[0]):
            self.coords[-1] = NounPhrase(self.coords[-1])
        self.coords[-1].add_complement(*mods, pos=pos)

    def add_post_modifier(self, *mods, pos=None):
        """ Add post modifiers to the last element. """
        # promote the element to a phrase
        if not is_phrase_t(self.coords[0]):
            self.coords[-1] = NounPhrase(self.coords[-1])
        self.coords[-1].add_post_modifier(*mods, pos=pos)

    def add_coordinate(self, *elts):
        """ Add one or more elements as a co-ordinate in the clause. """
        for e in str_to_elt(*elts):
            self.coords.append(e)

    def constituents(self):
        """ Return a generator to iterate through constituents. """
        yield self
        for c in self.coords:
            if hasattr(c, 'constituents'):
                yield from c.constituents()
            else:
                yield c

    def replace(self, one, another):
        """ Replace first occurance of one with another.
        Return True if successful.

        """
        logger.debug('Replacing "{}" in "{}" by "{}.'
                    .format(one, self, another))
        for i, o in enumerate(self.coords):
            if o == one:
                if another:
                    self.coords[i] = another
                else:
                    del self.coords[i]
                return True
            else:
                if o.replace(one, another):
                    return True
        return False

    @property
    def string(self):
        """Return the string inside the value. """
        return self.coords[0].string


class Phrase(Element):
    """ A base class for all kinds of phrases - elements containing other
        elements in specific places of the construct (front-, pre-, post-
        modifiers as well as the head of the phrase and any complements.

        Not every phrase has need for all of the kinds of modiffications.

    """

    def __init__(self, type=PHRASE, features=None, parent=None, **kwargs):
        super().__init__(type, features, parent)
        self.front_modifiers = list()
        self.pre_modifiers = list()
        self.head = Element()
        self.complements = list()
        self.post_modifiers = list()
        # see if anything was passed from above...
        if 'front_modifiers' in kwargs:
            self.front_modifiers = str_to_elt(*kwargs['front_modifiers'])
        if 'pre_modifiers' in kwargs:
            self.pre_modifiers = str_to_elt(*kwargs['pre_modifiers'])
        if 'head' in kwargs:
            self.head = kwargs['head']
        if 'complements' in kwargs:
            self.complements = str_to_elt(*kwargs['complements'])
        if 'post_modifiers' in kwargs:
            self.post_modifiers = str_to_elt(*kwargs['post_modifiers'])

    def __bool__(self):
        """ Return True """
        return True

    def __eq__(self, other):
        if not isinstance(other, Phrase):
            return False
        return (self._type == other._type and
                self.front_modifiers == other.front_modifiers and
                self.pre_modifiers == other.pre_modifiers and
                self.head == other.head and
                self.complements == other.complements and
                self.post_modifiers == other.post_modifiers and
                super().__eq__(other))

    def __hash__(self):
        assert False, 'Coordination Element is not hashable'

    def __iadd__(self, other):
        if is_adj_mod_t(other) or is_adv_mod_t(other):
            self.pre_modifiers.append(other)
        if isinstance(other, PrepositionalPhrase):
            self.add_complement(other)
        return self

    def __deepcopy__(self, memodict={}):
        copyobj = self.__class__(self._type, features=self.features, parent=self.parent)
        copyobj.id = self.id
        copyobj.front_modifiers = deepcopy(self.front_modifiers)
        copyobj.pre_modifiers = deepcopy(self.pre_modifiers)
        copyobj.head = deepcopy(self.head)
        copyobj.complements = deepcopy(self.complements)
        copyobj.post_modifiers = deepcopy(self.post_modifiers)
        return copyobj

    def accept(self, visitor, element='Phrase'):
        return super().accept(visitor, element)

    def set_front_modifiers(self, *mods):
        """ Set front-modifiers to the passed parameters. """
        self.front_modifiers = str_to_elt(*mods)

    def add_front_modifier(self, *mods, pos=0):
        """ Add one or more front-modifiers. """
        self._add_to_list(self.front_modifiers, *str_to_elt(*mods), pos=pos)

    def del_front_modifier(self, *mods):
        """ Remove one or more front-modifiers if present. """
        self._del_from_list(self.front_modifiers, *mods)

    def set_pre_modifiers(self, *mods):
        """ Set pre-modifiers to the passed parameters. """
        self.pre_modifiers = list(str_to_elt(*mods))

    def add_pre_modifier(self, *mods, pos=0):
        """ Add one or more pre-modifiers. """
        self._add_to_list(self.pre_modifiers, *str_to_elt(*mods), pos=pos)

    def del_pre_modifier(self, *mods):
        """ Delete one or more pre-modifiers if present. """
        self._del_from_list(self.pre_modifiers, *mods)

    def set_complements(self, *mods):
        """ Set complemets to the given ones. """
        self.complements = list(str_to_elt(*mods))

    def add_complement(self, *mods, pos=None):
        """ Add one or more complements. """
        self._add_to_list(self.complements, *str_to_elt(*mods), pos=pos)

    def del_complement(self, *mods):
        """ Delete one or more complements if present. """
        self._del_from_list(self.complements, *mods)

    def set_post_modifiers(self, *mods):
        """ Set post-modifiers to the given parameters. """
        self.post_modifiers = list(str_to_elt(*mods))

    def add_post_modifier(self, *mods, pos=None):
        """ Add one or more post-modifiers. """
        self._add_to_list(self.post_modifiers, *str_to_elt(*mods), pos=pos)

    def del_post_modifier(self, *mods):
        """ Delete one or more post-modifiers if present. """
        self._del_from_list(self.post_modifiers, *mods)

    def set_head(self, elt):
        """ Set head of the phrase to the given element. """
        if elt is None: elt = Element()
        self.head = String(elt) if isinstance(elt, str) else elt
        self.head.parent = self
        self.features.update(self.head.features)

    def yield_front_modifiers(self):
        """ Iterate through front modifiers. """
        for o in self.front_modifiers:
            for x in o.constituents():
                yield from x.constituents()

    def yield_pre_modifiers(self):
        """ Iterate through pre-modifiers. """
        for o in self.pre_modifiers:
            for x in o.constituents():
                yield from x.constituents()

    def yield_head(self):
        """ Iterate through the elements composing the head. """
        if self.head is not None:
            for x in self.head.constituents():
                yield from x.constituents()

    def yield_complements(self):
        """ Iterate through complements. """
        for o in self.complements:
            for x in o.constituents():
                yield from x.constituents()

    def yield_post_modifiers(self):
        """ Iterate throught post-modifiers. """
        for o in self.post_modifiers:
            for x in o.constituents():
                yield from x.constituents()

    def constituents(self):
        """ Return a generator to iterate through constituents. """
        yield self
        yield from self.yield_front_modifiers()
        yield from self.yield_pre_modifiers()
        yield from self.yield_head()
        yield from self.yield_complements()
        yield from self.yield_post_modifiers()

    # TODO: consider spliting the code below similarly to 'constituents()'
    def replace(self, one, another):
        """ Replace first occurance of one with another.
        Return True if successful.

        """
        for i, o in enumerate(self.front_modifiers):
            if o == one:
                if another is None:
                    del self.front_modifiers[i]
                else:
                    self.front_modifiers[i] = another
                return True
            else:
                if o.replace(one, another):
                    return True

        for i, o in enumerate(self.pre_modifiers):
            if o == one:
                if another is None:
                    del self.pre_modifiers[i]
                else:
                    self.pre_modifiers[i] = another
                return True
            else:
                if o.replace(one, another):
                    return True

        if self.head == one:
            for k in self.head.features.keys():
                if k in self.features:
                    del self.features[k]
            if hasattr(another, '_type') and self._type == another._type:
                if hasattr(self, 'spec') and hasattr(another, 'spec'):
                    self.spec = another.spec
                self.add_front_modifier(*another.front_modifiers)
                self.add_pre_modifier(*another.pre_modifiers)
                self.head = another.head
                self.add_complement(*another.complements)
                self.add_post_modifier(*another.post_modifiers)
            else:
                self.head = another
            self.features.update(another.features)
            return True
        elif self.head is not None:
            if self.head.replace(one, another):
                return True

        for i, o in enumerate(self.complements):
            if o == one:
                if another is None:
                    del self.complements[i]
                else:
                    self.complements[i] = another
                return True
            else:
                if o.replace(one, another):
                    return True

        for i, o in enumerate(self.post_modifiers):
            if o == one:
                if another is None:
                    del self.post_modifiers[i]
                else:
                    self.post_modifiers[i] = another
                return True
            else:
                if o.replace(one, another):
                    return True
        return False


class NounPhrase(Phrase):
    """
     * <UL>
     * <li>FrontModifier (eg, "some of")</LI>
     * <li>Specifier     (eg, "the")</LI>
     * <LI>PreModifier   (eg, "green")</LI>
     * <LI>Noun (head)   (eg, "apples")</LI>
     * <LI>complement    (eg, "that you liked")</LI>
     * <LI>PostModifier  (eg, "in the shop")</LI>
     * </UL>
     """

    def __init__(self, head=None, spec=None, features=None, parent=None, **kwargs):
        super().__init__(NOUN_PHRASE, features, parent, **kwargs)
        self.spec = None
        self.set_spec(spec)
        self.set_head(head)

    def __eq__(self, other):
        if not isinstance(other, NounPhrase):
            return False
        return (self.spec == other.spec and
                self.head == other.head and
                super().__eq__(other))

    def __deepcopy__(self, memodict={}):
        copyobj = self.__class__(deepcopy(self.head), deepcopy(self.spec),
                                 features=self.features, parent=self.parent)
        copyobj.id = self.id
        copyobj.hash = self.hash
        return copyobj

    def set_spec(self, spec):
        """ Set the specifier (e.g., determiner) of the NounPhrase. """
        if spec is None: spec = Element()
        # convert str to String if necessary
        self.spec = String(spec) if isinstance(spec, str) else spec  # use raise_to_element

    def constituents(self):
        """ Return a generator to iterate through constituents. """
        yield self
        if self.spec is not None:
            for c in self.spec.constituents(): yield from c.constituents()
        yield from self.yield_front_modifiers()
        yield from self.yield_pre_modifiers()
        yield from self.yield_head()
        yield from self.yield_complements()
        yield from self.yield_post_modifiers()

    def replace(self, one, another):
        """ Replace first occurance of one with another.
        Return True if successful.

        """
        if self.spec == one:
            self.spec = another
            return True
        elif self.spec is not None:
            if self.spec.replace(one, another): return True

        return super().replace(one, another)


class VerbPhrase(Phrase):
    """
    * <UL>
     * <LI>PreModifier      (eg, "reluctantly")</LI>
     * <LI>Verb             (eg, "gave")</LI>
     * <LI>IndirectObject   (eg, "Mary")</LI>
     * <LI>Object           (eg, "an apple")</LI>
     * <LI>PostModifier     (eg, "before school")</LI>
     * </UL>
     """

    def __init__(self, head=None, *compl, features=None, **kwargs):
        super().__init__(VERB_PHRASE, features, **kwargs)
        self.set_head(head)
        self.add_complement(*compl)

    def __deepcopy__(self, memodict={}):
        copyobj = self.__class__(deepcopy(self.head),
                                 features=self.features, parent=self.parent)
        copyobj.id = self.id
        copyobj.hash = self.hash
        copyobj.complements = deepcopy(self.complements)
        return copyobj

    def get_object(self):
        for c in self.complements:
            if c.has_feature('discourseFunction', 'OBJECT'):
                return c
        return None

    def remove_object(self):
        compls = list()
        for c in self.complements:
            if c.has_feature('discourseFunction', 'OBJECT'):
                continue
            else:
                compls.append(c)
        self.complements = compls

    def set_object(self, obj):
        self.remove_object()
        if obj is not None:
            if isinstance(obj, str): obj = String(obj)
            obj.set_feature('discourseFunction', 'OBJECT')
            self.complements.insert(0, obj)


class PrepositionalPhrase(Phrase):
    def __init__(self, head=None, *compl, features=None, **kwargs):
        super().__init__(PREPOSITIONAL_PHRASE, features, **kwargs)
        self.set_head(head)
        self.add_complement(*compl)

    def __deepcopy__(self, memodict={}):
        copyobj = self.__class__(deepcopy(self.head),
                                 features=self.features, parent=self.parent)
        copyobj.id = self.id
        copyobj.hash = self.hash
        copyobj.complements = deepcopy(self.complements)
        return copyobj


class AdverbPhrase(Phrase):
    def __init__(self, head=None, *compl, features=None, **kwargs):
        super().__init__(ADVERB_PHRASE, features, **kwargs)
        self.set_head(head)
        self.add_complement(*compl)

    def __deepcopy__(self, memodict={}):
        copyobj = self.__class__(deepcopy(self.head),
                                 features=self.features, parent=self.parent)
        copyobj.id = self.id
        copyobj.hash = self.hash
        copyobj.complements = deepcopy(self.complements)
        return copyobj


class AdjectivePhrase(Phrase):
    def __init__(self, head=None, *compl, features=None, **kwargs):
        super().__init__(ADJECTIVE_PHRASE, features, **kwargs)
        self.set_head(head)
        self.add_complement(*compl)

    def __deepcopy__(self, memodict={}):
        copyobj = self.__class__(deepcopy(self.head),
                                 features=self.features, parent=self.parent)
        copyobj.id = self.id
        copyobj.hash = self.hash
        copyobj.complements = deepcopy(self.complements)
        return copyobj


class Clause(Element):
    """ Clause - sentence.
    From simplenlg:
     * <UL>
     * <li>PreModifier (eg, "Yesterday")
     * <LI>Subject (eg, "John")
     * <LI>VerbPhrase (eg, "gave Mary an apple before school")
     * <LI>PostModifier (eg, ", didn't he?")
     * </UL>

    """

    subj = None
    vp = None

    def __init__(self, subj=None, vp=Element(), features=None, parent=None, **kwargs):
        super().__init__(CLAUSE, features, parent=parent)
        self.front_modifiers = list()
        self.pre_modifiers = list()
        self.set_subj(raise_to_np(subj))
        self.set_vp(raise_to_vp(vp))
        self.complements = list()
        self.post_modifiers = list()
        # see if anything was passed from above...
        if 'front_modifiers' in kwargs:
            self.front_modifiers = str_to_elt(*kwargs['front_modifiers'])
        if 'pre_modifiers' in kwargs:
            self.pre_modifiers = str_to_elt(*kwargs['pre_modifiers'])
        if 'complements' in kwargs:
            self.complements = str_to_elt(*kwargs['complements'])
        if 'post_modifiers' in kwargs:
            self.post_modifiers = str_to_elt(*kwargs['post_modifiers'])

    def __bool__(self):
        """ Return True """
        return True

    def __eq__(self, other):
        if not isinstance(other, Clause):
            return False
        return (self.pre_modifiers == other.pre_modifiers and
                self.subj == other.subj and
                self.vp == other.vp and
                self.complements == other.complements and
                self.post_modifiers == other.post_modifiers and
                super().__eq__(other))

    def __add__(self, other):
        other_ = deepcopy(other)
        self_ = deepcopy(self)
        if isinstance(other, Clause):
            return Coordination(self_, other_)
        if is_adj_mod_t(other):
            self_.subj += other_
            return self_
        if is_adv_mod_t(other):
            self_.vp += other_
            return self_
        else:
            raise ValueError('Cannot add these up: "{}" + "{}"'.format(self, other))

    def __deepcopy__(self, memodict={}):
        copyobj = self.__class__(deepcopy(self.subj),
                                 deepcopy(self.vp),
                                 features=self.features,
                                 parent=self.parent)
        copyobj.id = self.id
        copyobj.front_modifiers = deepcopy(self.front_modifiers)
        copyobj.pre_modifiers = deepcopy(self.pre_modifiers)
        copyobj.complements = deepcopy(self.complements)
        copyobj.post_modifiers = deepcopy(self.post_modifiers)
        return copyobj

    def set_subj(self, subj):
        """ Set the subject of the clause. """
        # convert str to String if necessary
        self.subj = String(subj) if isinstance(subj, str) else (subj or Element())
        self.subj.parent = self

    def set_vp(self, vp):
        """ Set the vp of the clause. """
        self.vp = String(vp) if isinstance(vp, str) else vp
        self.vp.parent = self

    # TODO: test
    def set_object(self, obj):
        object = String(obj) if isinstance(obj, str) else obj
        object.set_feature('discourseFunction', 'OBJECT')
        object.parent = self
        self.add_complement(object)

    def setfeatures(self, features):
        """ Set features on the VerbPhrase. """
        if self.vp:
            self.vp.setfeatures(features)
        else:
            self.features = features

    def constituents(self):
        """ Return a generator to iterate through constituents. """
        yield self
        yield from self.yield_pre_modifiers()
        yield from self.subj.constituents()
        yield from self.vp.constituents()
        yield from self.yield_complements()
        yield from self.yield_post_modifiers()

    def replace(self, one, another):
        """ Replace first occurance of one with another.
        Return True if successful.

        """
        if self.subj == one:
            self.subj = raise_to_np(another)
            self.subj.parent = self
            return True
        elif self.subj is not None:
            if self.subj.replace(one, another):
                return True

        if self.vp == one:
            self.vp = raise_to_vp(another)
            self.vp.parent = self
            return True
        elif self.vp is not None:
            if self.vp.replace(one, another):
                return True

        return super().replace(one, another)

    def set_front_modifiers(self, *mods):
        """ Set front-modifiers to the passed parameters. """
        self.front_modifiers = list(str_to_elt(*mods))

    def add_front_modifier(self, *mods, pos=0):
        """ Add one or more front-modifiers. """
        self._add_to_list(self.front_modifiers, *str_to_elt(*mods), pos=pos)

    def del_front_modifier(self, *mods):
        """ Remove one or more front-modifiers if present. """
        self._del_from_list(self.front_modifiers, *mods)

    def yield_front_modifiers(self):
        """ Iterate through pre-modifiers. """
        for o in self.front_modifiers:
            for x in o.constituents():
                yield from x.constituents()

    def set_pre_modifiers(self, *mods):
        """ Set pre-modifiers to the passed parameters. """
        self.pre_modifiers = list(str_to_elt(*mods))

    def add_pre_modifier(self, *mods, pos=0):
        """ Add one or more pre-modifiers. """
        self._add_to_list(self.pre_modifiers, *str_to_elt(*mods), pos=pos)

    def del_pre_modifier(self, *mods):
        """ Delete one or more pre-modifiers if present. """
        self._del_from_list(self.pre_modifiers, *mods)

    def yield_pre_modifiers(self):
        """ Iterate through pre-modifiers. """
        for o in self.pre_modifiers:
            for x in o.constituents():
                yield from x.constituents()

    def set_complements(self, *mods):
        """ Set complemets to the given ones. """
        self.complements = list(str_to_elt(*mods))

    def add_complement(self, *mods, pos=None):
        """ Add one or more complements. """
        self._add_to_list(self.complements, *str_to_elt(*mods), pos=pos)

    def del_complement(self, *mods):
        """ Delete one or more complements if present. """
        self._del_from_list(self.complements, *mods)

    def yield_complements(self):
        """ Iterate through complements. """
        for o in self.complements:
            for x in o.constituents():
                yield from x.constituents()

    def set_post_modifiers(self, *mods):
        """ Set post-modifiers to the given parameters. """
        self.post_modifiers = list(str_to_elt(*mods))

    def add_post_modifier(self, *mods, pos=None):
        """ Add one or more post-modifiers. """
        self._add_to_list(self.post_modifiers, *str_to_elt(*mods), pos=pos)

    def del_post_modifier(self, *mods):
        """ Delete one or more post-modifiers if present. """
        self._del_from_list(self.post_modifiers, *mods)

    def yield_post_modifiers(self):
        """ Iterate through pre-modifiers. """
        for o in self.post_modifiers:
            for x in o.constituents():
                yield from x.constituents()


def raise_to_np(phrase):
    """Take the current phrase and raise it to an NP.
    If `phrase` is a Noun it will be promoted to NP and used as a head;
    If `phrase` is a CC its coordinants will be raised to NPs

    """
    if isinstance(phrase, Coordination):
        phrase.coords = [raise_to_np(c) for c in phrase.coords]
        return phrase
    if isinstance(phrase, String):
        return NounPhrase(head=phrase)
    if isinstance(phrase, Word):
        return NounPhrase(head=phrase)
    # if isinstance(phrase, Var):
    #     return NounPhrase(head=phrase)
    return phrase


def raise_to_vp(phrase):
    """Take the current phrase and raise it to a VP.
    If `phrase` is a Word it will be promoted to VP and used as a head;
    If `phrase` is a CC its coordinants will be raised to VPs

    """
    if isinstance(phrase, Coordination):
        phrase.coords = [raise_to_vp(c) for c in phrase.coords]
        return phrase
    if isinstance(phrase, String):
        return VerbPhrase(head=phrase)
    if isinstance(phrase, Word):
        return VerbPhrase(head=phrase)
    # if isinstance(phrase, Var):
    #     return VerbPhrase(head=phrase)
    return phrase


def raise_to_element(element):
    """Raise the given thing to an element (e.g., String). """
    if not isinstance(element, Element):
        return String(str(element))  # use str() in case of numbers
    return element
