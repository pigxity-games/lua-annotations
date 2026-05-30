local ReplicatedStorage = game:GetService('ReplicatedStorage')
local ManifestAPI = require(ReplicatedStorage.Generated._Internal.ManifestAPI)
local ServerScriptService = game:GetService('ServerScriptService')

return ManifestAPI.new({
	environment = 'server',
	modulePaths = {
		Lifecycle = {ReplicatedStorage, 'Generated', '_Internal', 'Lifecycle'},
		SomeModule = {ReplicatedStorage, 'SomeModule'},
		MyService = {ServerScriptService, 'MyService'},
		MyService2 = {ServerScriptService, 'MyService2'},
	},
	manifest = {
		hooks = {
			pre_init = {},
			annotation_handlers = {
				remote = {
					module = 'Lifecycle',
					method = 'remote',
				},
			},
			module_handlers = {
				{
					module = 'Lifecycle',
					method = 'initService',
				},
			},
			post_init = {
				{
					module = 'SomeModule',
					method = 'somePostInitHook',
				},
			},
		},
		modules = {
			MyService = {
				annotations = {
					printMessage = {
						{
							name = 'remote',
							args = {
								'function',
							},
							kwargs = {},
							data = {},
						},
					},
				},
				data = {
					kind = 'service',
					depends = {
						services = {'MyService2'},
						remotes = {},
					},
				},
			},
			MyService2 = {
				annotations = {
					_module = {
						{
							name = 'someModuleAnnotationWithCustomData',
							args = {},
							kwargs = {},
							data = {
								keyInjectedByPython = 'valueInjectedByPython',
							},
						},
					},
				},
				data = {
					kind = 'service',
					depends = {
						services = {},
						remotes = {'ClientDataController'},
					},
				},
			},
		},
		load_order = {'MyService2', 'MyService'},
		remotes = {
			client = {},
			server = {},
		},
	},
})
