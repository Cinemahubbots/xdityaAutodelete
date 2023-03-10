# best regards, ChatGPT
# Redistribution is not allowed.


def time_formatter(time_input):
    num = int(time_input[:-1])
    unit = time_input[-1]
    # Convert time to seconds based on unit
    if unit == "h":
        total_seconds = num * 3600
    elif unit == "m":
        total_seconds = num * 60
    elif unit == "s":
        total_seconds = num
    else:
        return None
    return total_seconds
