# Query Data with AWS Athena

```SQL
SELECT DISTINCT token, line_item.title AS title
FROM test12
CROSS JOIN UNNEST(line_items) AS t(line_item);
```

# Deploy

Build artifacts.

```bash
sam build --base-dir lambda_code
```

Upload artifacts to S3.

```bash
sam package --s3-bucket <deployment bucket> --output-template-file .deployment/template.yml --s3-prefix shopify_data_lake
```

Create stack.

```bash
sam deploy --template-file .deployment/template.yml --stack-name <stack name> --capabilities CAPABILITY_NAMED_IAM --parameter-overrides $(cat .deployment/parameters)
```

Note that `.deployment/parameters` should be of the format:

```
<parameter key>=<parameter value>
...
```

# Test Locally

Build artifacts.

```bash
sam build --base-dir lambda_code
```

Run code.

```bash
sam local invoke --event .test/events/authentic_request.json --env-vars .test/env_vars.json HandleCartEventFunction
```

For multiple tests, run:

```bash
sam local start-lambda --env-vars .test/env_vars.json
```

Invoke:

```bash
aws lambda invoke --function-name HandleCartEventFunction --endpoint-url http://127.0.0.1:3001 --no-verify-ssl --payload "$(cat .test/events/authentic_request.json)" /dev/null
aws lambda invoke --function-name HandleCartEventFunction --endpoint-url http://127.0.0.1:3001 --no-verify-ssl --payload "$(cat .test/events/digest_does_not_match.json)" /dev/null
aws lambda invoke --function-name HandleCartEventFunction --endpoint-url http://127.0.0.1:3001 --no-verify-ssl --payload "$(cat .test/events/invalid_request.json)" /dev/null
```

Logs will show up in terminal where Lambda was started.

# TODO: Make less specific to my environment

Environment variables file contains a mapping from Lambda function logical resource id (e.g., 'HandleCartEventFunction')
to key to value.

# Overview of Design
