from twisted.internet.defer import DeferredList
from buildbot.util import islist

class ChainedBuilder:
    ''' A helper class to simplify the algorithm in BuildSet.orderedStart '''

    first = False
    next_el = None

    def __init__(self, builder, request, next_el):
        # 'builder' must be a Builder instance or a list of Builder instances.
        # In case of the latter, 'requests' (which must also be a list of
        # the corresponding BuildRequests) are submitted simultaneously

        assert isinstance(next_el, ChainedBuilder) or next_el is None

        self.builder = builder
        self.request = request
        self.next_el = next_el
        self.name = islist(builder) and [i.name for i in builder]\
                                    or  builder.name

    def getChainAsList(self):
        current = self
        while True:
            yield current
            current = current.next_el
            if current == None: break

    def __repr__(self):
        return "<%s> %s" % (self.__class__.__name__, self.name)

    def waitUntilFinished(self):
        # If we're holding on to a list of Builders, we return 
        # a DeferredList and the Deferreds that it's made of.
        if islist(self.builder):
            deferreds = []
            for req in self.request:
                deferreds.append(req.waitUntilFinished())
            dl = DeferredList(deferreds, fireOnOneErrback=True)
            return dl, deferreds
        else:
            return self.request.waitUntilFinished()

    def submitBuildRequest(self):
        if islist(self.builder):
            for b,r in zip(self.builder, self.request):
                b.submitBuildRequest(r)
        else:
            self.builder.submitBuildRequest(self.request)

    def getNamedOrder(self):
        names = []
        names.append(self.name)
        
        if self.next_el:
            names.extend(self.next_el.getNamedOrder())
        else:
            names = [self.name]
        
        return names
