import json


def filter_non_zero_values(d):
    new_dict = {}
    for key, nested_dict in d.items():
        new_dict[key] = {k: v for k, v in nested_dict.items() if v != 0}
    return new_dict


# Load the JSON file
with open('tokensniffer_cache_old.json', 'r') as f:
    data = json.load(f)

# Filter out pairs where the value is not zero
filtered_data = filter_non_zero_values(data)

# Write the filtered data to a new JSON file
with open('tokensniffer_cache.json', 'w') as f:
    json.dump(filtered_data, f)
