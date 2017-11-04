def chunk_string(string, chunk_size=450):
    # Limit = 462, cutting off at 450 to be safe.
    string_chunks = []

    while len(string) != 0:
        current_chunk = string[0:chunk_size]
        string_chunks.append(current_chunk)
        string = string[len(current_chunk):]
    return string_chunks
