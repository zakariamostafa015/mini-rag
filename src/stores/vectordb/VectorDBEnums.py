from enum import Enum

class VectorDBEnums(str, Enum):
    QDRANT = "QDRANT"

class DistanceMethodEnums(str, Enum):
    COSINE = "cosine"
    DOT = "dot"
    EUCLIDEAN = "euclidean"