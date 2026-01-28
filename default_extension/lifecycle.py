from annotations import AnnotationDef
from arguments import list_arg

service = AnnotationDef('service', kwargs={
    'depends': list_arg
})

indexed = AnnotationDef('indexed', retention='build')
indexedType = AnnotationDef('indexedType', scope='type', retention='build')