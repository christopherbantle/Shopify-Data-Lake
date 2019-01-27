# Shopify Data Lake

An AWS SAM project that will enable you to create an S3 data lake with your Shopify store's cart and checkout events.

The application works as follows:

![Diagram](architecture.png)

Shopify sends events (in particular, `carts/create`, `carts/update`, `checkouts/create`, and `checkouts/update` events) 
to an API Gateway endpoint.  API Gateway will then invoke a Lambda function asynchronously, and return a response
to Shopify, without waiting for the results of the Lambda invocation.  The Lambda function will put the
data into a Kinesis Firehose, from which it will be saved in batches to S3.

## Query Data with Athena

Note that some event attributes are omitted in the table creation.  For a description of all event attributes, see [here](https://help.shopify.com/en/api/reference/events/webhook). 

### Create Database for Shopify Events

```SQL
CREATE DATABASE shopify_events;
```

### Create Table for Cart Events

```SQL
CREATE EXTERNAL TABLE shopify_events.carts (
  token string,
  updated_at string,
  created_at string,
  line_items array<struct< 
  quantity:int,
  title:string,
  price:string
>> 
) 
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://<data bucket>/cart/';
```

### Create View For Cart Line Items

```SQL
CREATE OR REPLACE VIEW shopify_events.cart_line_items AS
SELECT token, cast(from_iso8601_timestamp(updated_at) AS TIMESTAMP) AS update_time, cast(from_iso8601_timestamp(created_at) AS TIMESTAMP) AS creation_time, line_item.quantity AS quantity, line_item.title AS title, cast(line_item.price AS DECIMAL) AS price
FROM shopify_events.carts
CROSS JOIN UNNEST(line_items) AS t(line_item);
```

### Get Most Recent State of Carts

For each cart in its most recent state, there will be one row per line item.

```SQL
SELECT a.*
FROM shopify_events.cart_line_items a
INNER JOIN (
    SELECT token, max(update_time) as last_update_time
    FROM shopify_events.cart_line_items
    GROUP BY token
) b ON a.token = b.token AND a.update_time = b.last_update_time;
```

### Get All Items Added to Carts

```SQL
SELECT token, title, max(quantity) as max_quantity
FROM shopify_events.cart_line_items
GROUP BY token, title;
```

### Create Table for Checkout Events

```SQL
CREATE EXTERNAL TABLE shopify_events.checkouts (
  token string,
  cart_token string,
  updated_at string,
  created_at string,
  completed_at string,
  line_items array<struct< 
  quantity:int,
  title:string,
  price:string
>>,
  customer struct<
   id:string
>
) 
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://<data bucket>/checkout/';
```

### Create View for Checkout Line Items

```SQL
CREATE OR REPLACE VIEW shopify_events.checkout_line_items AS
SELECT token AS checkout_token, cart_token, cast(from_iso8601_timestamp(updated_at) AS TIMESTAMP) AS update_time, cast(from_iso8601_timestamp(created_at) AS TIMESTAMP) AS creation_time, cast(from_iso8601_timestamp(completed_at) AS TIMESTAMP) AS completion_time, line_item.quantity AS quantity, line_item.title AS title, cast(line_item.price AS DECIMAL) AS price, customer.id AS customer_id
FROM shopify_events.checkouts
CROSS JOIN UNNEST(line_items) AS t(line_item);
```

### Get Most Recent State of Checkouts

```SQL
SELECT DISTINCT a.*
FROM shopify_events.checkout_line_items a
INNER JOIN (
    SELECT checkout_token, max(update_time) as last_update_time
    FROM shopify_events.checkout_line_items
    GROUP BY checkout_token
) b ON a.checkout_token = b.checkout_token AND a.update_time = b.last_update_time;
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
