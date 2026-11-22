import itertools

MODULUS = 65537


def direct(blocks, kind, operand=None):
    results = []
    for a in blocks:
        size = len(a)
        c = [[0 for _ in range(size)] for _ in range(size)]
        for row in range(size):
            for col in range(size):
                for inner in range(size):
                    if kind == 'linear':
                        c[row][col] += a[row][inner] * operand[inner][col]
                    elif kind == 'gram':
                        c[row][col] += a[inner][row] * a[inner][col]
                    else:
                        raise ValueError('UNKNOWN_REFERENCE_OPERATION')
                c[row][col] %= MODULUS
        results.append(c)
    return results


def accept(blocks, kind, operand, received):
    return received == direct(blocks, kind, operand)


def conventional_coded(kind, losses=1):
    q = 3 if kind == 'linear' else 5
    slots = list(itertools.product(range(3), range(3)))
    for count in range(1, 10):
        feasible = []
        for subset in itertools.combinations(slots, count):
            if all(sum(d not in lost for d, s in subset) >= q
                   for lost in itertools.combinations(range(3), losses)):
                feasible.append(subset)
        if feasible:
            return {'worker_units': count, 'feasible_placements': len(feasible)}
    return None


def replication(losses=1):
    slots = list(itertools.product(range(3), range(3)))
    for count in range(3, 10):
        for subset in itertools.combinations(slots, count):
            for assignments in itertools.product(range(3), repeat=count):
                if set(assignments) != {0, 1, 2}:
                    continue
                if all({a for (d, s), a in zip(subset, assignments) if d not in lost} == {0, 1, 2}
                       for lost in itertools.combinations(range(3), losses)):
                    return {'worker_units': count, 'workers': [
                        {'domain': d, 'slot': s, 'block': b} for (d, s), b in zip(subset, assignments)]}
    return None
