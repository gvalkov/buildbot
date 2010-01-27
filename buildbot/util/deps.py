from util import flatten

def walkDependencyDict(dependencies, group_parallel=True):
    '''
    >>> dep = {'A' : ['B', 'C'],
    ...        'B' : ['D'],
    ...        'C' : [],
    ...        'D' : [],
    ...       }
    >>> print walkDependencyDict(dep)
    [['C', 'D'], 'B', 'A']
    >>> print walkDependencyDict(dep, False)
    ['C', 'D', 'B', 'A']
    '''
    
    def getIndependent():
        return [i for i in items if not doesDepend(i)]
    
    def doesDepend(item):
        if not item in dependencies: return False
        return any(i not in walked for i in dependencies[item])
    
    items = set(dependencies.keys())
    walked = set()
    result = []
    
    while True:
        if not items: break
        
        indep =  set(getIndependent())

        # items := elements that are in 'items' but not in 'indep' 
        items = items.difference(indep) 

        # walked := elements that are both in 'walked' and 'indep'
        walked = walked.union(indep)

        result.append(indep)
        
        if set(sum(dependencies.values(), [])) == walked:
            result.append(items)
            break
        
    if group_parallel:
        for i,j in enumerate(result):
            if len(j) > 1: result[i] = list(j)
            else: result[i] = list(j)[0]
    else:
        result = flatten(result)
        
    return result
    

def getDependencies(item, dependencies, inclself=True):
    '''
    >>> dep = {'A' : ['B', 'D'],
    ...        'B' : ['C', 'E'],
    ...        'C' : ['D', 'E'],
    ...        'D' : [],
    ...        'E' : [],
    ...        'F' : [],
    ...        'G' : [],
    ...       }
    >>> print getDependencies('A', dep)
    ['D', 'E', 'C', 'B', 'A']
    >>> print getDependencies('A', dep, False)
    ['D', 'E', 'C', 'B']
    >>> dep['D'] = ['A']
    >>> getDependencies('A', dep)
    Traceback (most recent call last):
        ...
    Exception: Circular dependency: D <-> A
    >>> print getDependencies('E', dep)
    ['E']
    ''' 
    
    if item not in dependencies.keys():
        raise Exception('"%s" not in dependency graph' % item)
    
    resolved = []
    unresolved = []
    
    def _helper(item):
        unresolved.append(item)
        for dep in dependencies[item]:
            if dep not in resolved:
                if dep in unresolved:
                    raise Exception('Circular dependency: %s <-> %s' % (item, dep))
                _helper(dep)
        resolved.append(item)
        unresolved.remove(item)
    
    _helper(item)
    
    if not inclself:
        resolved.pop(resolved.index(item))
    return resolved
