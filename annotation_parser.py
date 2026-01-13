from typing import Literal, TypedDict

class AnnotationArg():
    pass

class AnnotationOptions(TypedDict):
    args: list[str]
    type: Literal['build', 'boot', 'runtime'] 

class AnnotationDef():
    def __init__(self, name: str, options: AnnotationOptions):
        pass

class Annotation():
    def __init__(self, definition: AnnotationDef, text: str):
        pass
