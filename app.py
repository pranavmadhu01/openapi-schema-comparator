from flask import Flask, render_template, request
import json
from jsonschema import ValidationError
from utils.validationUtils import ValidationUtils as v

app = Flask(__name__)


def add_additional_properties_false(schema):

    if isinstance(schema, dict):
        if schema.get("type") == "object" and "additionalProperties" not in schema:
            schema["additionalProperties"] = False

        for key, value in schema.items():
            add_additional_properties_false(value)

    elif isinstance(schema, list):
        for item in schema:
            add_additional_properties_false(item)

    return schema


def extract_schema_for_method(schema, path, method):
    """Extract request and response schemas for a specific path and method."""
    path_item = schema.get("paths", {}).get(path, {})
    method_item = path_item.get(method.lower(), {})

    # Extract request body schema
    request_body = (
        method_item.get("requestBody", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema", None)
    )

    # Extract response schema (assuming we want 200 OK responses)
    response_body = (
        method_item.get("responses", {})
        .get("200", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema", None)
    )

    # Dereference the schemas
    if request_body:
        request_body = dereference_schema(schema, request_body)

    if response_body:
        response_body = dereference_schema(schema, response_body)

    return {"request_schema": request_body, "response_schema": response_body}


def dereference_schema(root_schema, schema):
    """Recursively dereference $ref in the schema, handling oneOf, allOf, anyOf, and not."""
    if isinstance(schema, dict) and "$ref" in schema:
        # Dereference the $ref
        ref_path = schema["$ref"]
        ref_parts = ref_path.split("/")
        ref_section = ref_parts[1]  # "components"
        ref_type = ref_parts[2]      # "schemas"
        ref_name = ref_parts[3]      # "SomeSchema"

        # Get the actual referenced schema
        referenced_schema = root_schema.get(ref_section, {}).get(ref_type, {}).get(ref_name, {})

        # Recursively dereference the referenced schema
        return dereference_schema(root_schema, referenced_schema)

    # Handle combinators (oneOf, allOf, anyOf, not)
    if isinstance(schema, dict):
        if "oneOf" in schema:
            # Replace oneOf with the first schema in the list, and dereference it
            first_schema = schema["oneOf"][0]
            return dereference_schema(root_schema, first_schema)
        
        if "allOf" in schema:
            # Recursively dereference each schema in allOf and merge them
            first_schema = schema["allOf"][0]
            return dereference_schema(root_schema, first_schema)
        
        if "anyOf" in schema:
            # Recursively dereference each schema in anyOf
            schema["anyOf"] = [dereference_schema(root_schema, sub_schema) for sub_schema in schema["anyOf"]]
        
        if "not" in schema:
            # Recursively dereference the schema in not
            schema["not"] = dereference_schema(root_schema, schema["not"])

        # Recursively process other fields (for nested schemas)
        return {key: dereference_schema(root_schema, value) for key, value in schema.items()}
    
    elif isinstance(schema, list):
        return [dereference_schema(root_schema, item) for item in schema]
    
    return schema

@app.route("/", methods=["GET", "POST"])
def index():
    openapi_schema_data = ""
    paths = []
    request_schema = None
    response_schema = None
    selected_path = None
    request_data = ""
    response_data = ""
    request_validation_errors = []
    response_validation_errors = []

    if request.method == "POST":
        # Get the OpenAPI schema and data
        openapi_schema_data = request.form.get("openapi_schema")
        selected_path = request.form.get("selected_path")
        request_data = request.form.get("request_data")
        response_data = request.form.get("response_data")

        try:
            # Load the OpenAPI schema JSON
            openapi_schema = json.loads(openapi_schema_data)
            paths = openapi_schema.get("paths", {})
            # Parse the selected path for response schema
            if selected_path:
                schemas = extract_schema_for_method(openapi_schema,selected_path,"post")
                request_schema = schemas.get("request_schema",{})
                response_schema = add_additional_properties_false(schemas.get("response_schema",{}))                
                # Validate the request data if provided
                if request_data and request_schema:
                    try:
                        request_json = json.loads(request_data)
                        errors = v.validate_openapi_schema(instance=request_json, schema=request_schema)
                        request_validation_errors = errors
                    except ValidationError as ve:
                        request_validation_errors.append(f"Request validation failed: {str(ve)}")
                    except json.JSONDecodeError:
                        request_validation_errors.append("Invalid request JSON format.")

                # Validate the response data if provided
                if response_data and response_schema:
                    try:
                        response_json = json.loads(response_data)
                        errors = v.validate_openapi_schema(instance=response_json, schema=response_schema)
                        response_validation_errors = errors
                    except ValidationError as ve:
                        response_validation_errors.append(f"Response validation failed: {str(ve)}")
                    except json.JSONDecodeError:
                        response_validation_errors.append("Invalid response JSON format.")

        except json.JSONDecodeError:
            request_validation_errors.append("Invalid OpenAPI JSON format.")

    return render_template(
        "index.html",
        openapi_schema_data=openapi_schema_data,
        paths=paths,
        selected_path=selected_path,
        request_schema=request_schema,
        response_schema=response_schema,
        request_data=request_data,
        response_data=response_data,
        request_validation_errors=request_validation_errors,
        response_validation_errors=response_validation_errors
    )



if __name__ == "__main__":
    app.run(debug=True)
