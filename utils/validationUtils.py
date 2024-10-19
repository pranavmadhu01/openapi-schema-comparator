from jsonschema import Draft7Validator


class ValidationUtils:

    def __init__(self) -> None:
        pass

    def validate_openapi_schema(schema, instance):
        validator = Draft7Validator(schema)
        errors = list(validator.iter_errors(instance))

        if errors:
            error_messages = []
            for error in errors:
                error_messages.append(f"Error: {error.message} at path {list(error.path)} at schema path {list(error.schema_path)}")
                
            return error_messages
        else:
            return []
    