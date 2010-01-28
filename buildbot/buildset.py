from buildbot.process import base
from buildbot.status import builder
from buildbot.process.properties import Properties
from buildbot.util.deps import walkDependencyDict
from buildbot.util import flatten, islist
from buildbot.util.chainedbuilder import ChainedBuilder
from twisted.python import log


class BuildSet:
    """I represent a set of potential Builds, all of the same source tree,
    across a specified list of Builders. I can represent a build of a
    specific version of the source tree (named by source.branch and
    source.revision), or a build of a certain set of Changes
    (source.changes=list)."""

    def __init__(self, builderNames, source, reason=None, bsid=None,
                 properties=None):
        """
        @param source: a L{buildbot.sourcestamp.SourceStamp}
        """
        self.builderNames = builderNames
        self.source = source
        self.reason = reason

        self.properties = Properties()
        if properties: self.properties.updateFromProperties(properties)

        self.stillHopeful = True
        self.status = bss = builder.BuildSetStatus(source, reason,
                                                   builderNames, bsid)

    def waitUntilSuccess(self):
        return self.status.waitUntilSuccess()

    def waitUntilFinished(self):
        return self.status.waitUntilFinished()

    def getProperties(self):
        return self.properties

    def start(self, builders):
        if isinstance(builders, dict):
            self.orderedStart(builders)

        elif isinstance(builders, (list, tuple)):
            self.simultaneousStart(builders)

    def simultaneousStart(self, builders):
        """This is called by the BuildMaster to actually create and submit
           the BuildRequests simultaneously.
        """

        self.requests = []
        reqs = []

        # create the requests
        for b in builders:
            req = base.BuildRequest(self.reason, self.source, b.name, 
                                    properties=self.properties)
            reqs.append((b, req))
            self.requests.append(req)
            d = req.waitUntilFinished()
            d.addCallback(self.requestFinished, req)

        # tell our status about them
        req_statuses = [req.status for req in self.requests]
        self.status.setBuildRequestStatuses(req_statuses)

        # now submit them
        for b,req in reqs:
            b.submitBuildRequest(req)

    def orderedStart(self, builders):
        """This is called by the BuildMaster to actually create and submit
           the BuildRequests in an ordered manner.
           @param: builders: should be a dictionary mapping builders to their
                   prerequisite builders
        """

        self.requests = []
        requests = {}
 
        # get the order in which BuildRequests should be submitted. Unfolded
        # is a list, such as [[A,B], C, D]. This conveys the following
        # dependency - send the requests for [A,B] simultaneously ; once they're
        # done trigger C ; once C is done trigger D
        
        unfolded = walkDependencyDict(builders)

        # create the BuildRequest for each builder in advance
        for b in flatten(unfolded):
            requests[b] = base.BuildRequest(self.reason, self.source, b.name,
                                            properties=self.properties)


        # create the ChainedBuilder structure. It is a singly-linked list 
        # representation of the 'unfolded' list
        next_el = None
        for builder in reversed(unfolded):
            if islist(builder):
                reqs = [requests[i] for i in builder]
            else:
                reqs = requests[builder]

            current_el = ChainedBuilder(builder, reqs, next_el)
            next_el = current_el

        first_el = current_el
        current_el.first = True

        #log.msg('builder order: ' + str(first_el.getNamedOrder()))

        # Process the ChainedBuilder structure. There is a lot of
        # redundancy here, but it does make the code appear more
        # linear and understandable
        while True:

            # If we are dealing with the first element of the list
            # we need to submit its request (it is the entry point)
            if current_el.first:

                # If they need to be triggered simultaneously 
                if islist(current_el.builder):
                    dl, deferreds = current_el.waitUntilFinished()

                    # 'dl' is a DeferredList that will callback when 
                    # 'deferreds' callback

                    for d,r in zip(deferreds, current_el.request):
                        self.requests.append(r)
                        d.addCallback(self.requestFinished, r)

                else:
                    dl = current_el.waitUntilFinished()
                    dl.addCallback(self.requestFinished, current_el.request)

                # submit requests (if current_el holds a list, its requests will
                # be submitted simultaneously)
                current_el.submitBuildRequest()

                # Once the request callbacks we tell it to trigger the next
                # ChainedBuilder in line
                dl.addCallback(self._triggerNext, current_el.next_el)
            
            else:
                if islist(current_el.builder):
                    dl, deferreds = current_el.waitUntilFinished()
                else:
                    dl = current_el.waitUntilFinished()

                dl.addCallback(self._triggerNext, current_el.next_el)

            #print '%s will trigger %s' % (current_el.name, current_el.next_el.name)

            current_el = current_el.next_el
            if current_el is None: break

        req_statuses = []
        for cb in first_el.getChainAsList():
            if islist(cb.request):
                req_statuses.extend(req.status for req in cb.request)
            else:
                req_statuses.append(cb.request.status)

        self.status.setBuildRequestStatuses(req_statuses)


    def _triggerNext(self, *args):
        next_el = args[-1]
        #print '_triggerNext:', next_el.name
        #self.requests.append(next_el.request)

        if next_el is None: return
        
        if islist(next_el.request):
            self.requests.extend(next_el.request)
            dl, deferreds = next_el.waitUntilFinished()
            for d,r in zip(deferreds, next_el.request):
                d.addCallback(self.requestFinished, r)

        else:
            self.requests.append(next_el.request)
            d = next_el.waitUntilFinished()
            d.addCallback(self.requestFinished, next_el.request)

        next_el.submitBuildRequest()

    def requestFinished(self, buildstatus, req):
        # TODO: this is where individual build status results are aggregated
        # into a BuildSet-wide status. Consider making a rule that says one
        # WARNINGS results in the overall status being WARNINGS too. The
        # current rule is that any FAILURE means FAILURE, otherwise you get
        # SUCCESS.
        self.requests.remove(req)
        results = buildstatus.getResults()
        if results == builder.FAILURE:
            self.status.setResults(results)
            if self.stillHopeful:
                # oh, cruel reality cuts deep. no joy for you. This is the
                # first failure. This flunks the overall BuildSet, so we can
                # notify success watchers that they aren't going to be happy.
                self.stillHopeful = False
                self.status.giveUpHope()
                self.status.notifySuccessWatchers()
        if not self.requests:
            # that was the last build, so we can notify finished watchers. If
            # we haven't failed by now, we can claim success.
            if self.stillHopeful:
                self.status.setResults(builder.SUCCESS)
                self.status.notifySuccessWatchers()
            self.status.notifyFinishedWatchers()

