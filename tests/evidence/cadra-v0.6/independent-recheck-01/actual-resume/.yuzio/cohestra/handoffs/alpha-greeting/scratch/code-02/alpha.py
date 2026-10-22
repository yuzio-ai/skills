def greet(name):
    name = name.strip()
    return f"Hello, {name or 'world'}!"
