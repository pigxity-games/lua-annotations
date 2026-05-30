local WINDOW_SECONDS = 5
local MAX_REQUESTS = 10

local buckets = {}

--@middleware, server, inbound, global=true
local function RateLimit(ctx, ...)
	local player = ctx.player
	if not player then
		return true, ...
	end

	local now = os.clock()
	local bucket = buckets[player]

	if not bucket or now - bucket.startedAt > WINDOW_SECONDS then
		bucket = {
			startedAt = now,
			count = 0,
		}
		buckets[player] = bucket
	end

	bucket.count += 1

	if bucket.count > MAX_REQUESTS then
		print("Ratelimited: " .. player.Name)
		return false, {
			status = "error",
			message = "You are sending requests too quickly.",
		}
	end

	return true, ...
end

return RateLimit
