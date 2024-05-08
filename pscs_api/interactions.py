from __future__ import annotations
from copy import deepcopy

interaction_parameter_string = "param"
interaction_fstring = interaction_parameter_string + "[{param}]"
interaction_pattern = f"{interaction_parameter_string}\\[(.*?)\\]"


def istr(arg):
    return interaction_fstring.format(param=arg)

class InteractionList:
    def __init__(self, *args, **kwargs):
        self.interactions = [a for a in args]  # For adding defined Interactions
        new_interaction = Interaction()  # for defining a simple interaction directly in the list
        keep = False
        for k, v in kwargs.items():
            for vv in v:
                getattr(new_interaction, k).add(vv)
                keep = True
        if keep:
            self.interactions.append(new_interaction)
        return

    def __mul__(self, other):
        prod = InteractionList()
        if len(other) == 0:
            return deepcopy(self)
        if len(self) == 0:
            return deepcopy(other)
        for self_interaction in self.interactions:
            for other_interaction in other.interactions:
                prod.interactions.append(self_interaction + other_interaction)
        return prod

    def product(self, other):
        """In-place multiplication."""
        prod = self * other
        self.interactions = prod.interactions
        return

    def __len__(self):
        return len(self.interactions)

    def __getitem__(self, index):
        return self.interactions[index]

    def __gt__(self, other):
        if len(other) == 0:
            return True
        for self_interaction in self.interactions:
            for other_interaction in other.interactions:
                if self_interaction > other_interaction:
                    return True
        return False

    def __eq__(self, other):
        for self_interaction in self.interactions:
            for other_interaction in other.interactions:
                if self_interaction == other_interaction:
                    return True
        return False

    def __ge__(self, other):
        if len(other) == 0:
            return True
        for self_interaction in self.interactions:
            for other_interaction in other.interactions:
                if self_interaction >= other_interaction:
                    return True
        return False

    def __lt__(self, other):
        return not self >= other

    def __le__(self, other):
        return not self > other

    def __add__(self, other):
        summed = InteractionList()
        if len(self.interactions) != len(other.interactions):
            raise ValueError("Addition on InteractionLists can only be added together when the lists have the same "
                             "number of interactions.")
        for self_interaction, other_interaction in zip(self.interactions, other.interactions):
            summed.interactions.append(self_interaction + other_interaction)
        return summed

    def __str__(self):
        interactions = [str(i) for i in self.interactions]
        return "\n".join(interactions)


class Interaction:
    def __init__(self,
                 obs: set = None,
                 var: set = None,
                 var_names: set = None,
                 obsm: set= None,
                 varm: set = None,
                 uns: set = None,
                 obsp: set = None,
                 layers: set = None):
        self.obs = set(obs) if obs is not None else set()
        self.var = set(var) if var is not None else set()
        self.var_names = set(var_names) if var_names is not None else set()
        self.obsm = set(obsm) if obsm is not None else set()
        self.varm = set(varm) if varm is not None else set()
        self.uns = set(uns) if uns is not None else set()
        self.obsp = set(obsp) if obsp is not None else set()
        self.layers = set(layers) if layers is not None else set()
        return

    def __gt__(self, other: Interaction):
        """Checks whether one interaction is a superset of the other. Useful for comparing against requirements."""
        for var in vars(self):
            if not getattr(self, var) > getattr(other, var):
                return False
        return True

    def __eq__(self, other: Interaction):
        for var in vars(self):
            if not getattr(self, var) == getattr(other, var):
                return False
        return True

    def __ge__(self, other: Interaction):
        for var in vars(self):
            if not getattr(self, var) >= getattr(other, var):
                return False
        return True

    def __lt__(self, other: Interaction):
        return not (self > other or self == other)

    def __le__(self, other: Interaction):
        return not (self > other)

    def __add__(self, other: Interaction):
        summed = Interaction()
        for var in vars(self):
            getattr(summed, var).update(getattr(self, var))
            getattr(summed, var).update(getattr(other, var))
        return summed

    def __str__(self):
        return f"obs: {sorted(self.obs)}, var: {sorted(self.var)}, var_names: {sorted(self.var_names)}, obsm: {sorted(self.obsm)}, varm: {sorted(self.varm)}, uns: {sorted(self.uns)}, layers: {sorted(self.layers)}"

    def add(self, other: Interaction):
        """Extends this object's attributes to include those in the argument."""
        for var in vars(self):
            getattr(self, var).update(getattr(other, var))
        return
