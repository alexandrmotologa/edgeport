# Webhook Inspection, Mocking, and Replay

Testing third-party webhooks from services like Stripe, GitHub, Twilio, and Shopify requires handling asynchronous HTTP POST requests sent directly to a publicly accessible URL.

EdgePort captures every incoming webhook payload, presents the headers and payload in structured format, and allows replaying the request against your local application repeatedly without triggering the external provider.

## Common Webhook Headers Captured

EdgePort recognizes and highlights signature headers from major webhook providers:

| Provider | Signature Header | Event Type Header |
| :--- | :--- | :--- |
| Stripe | `Stripe-Signature` | Included in JSON payload (`type`) |
| GitHub | `X-Hub-Signature-256` | `X-GitHub-Event` |
| Shopify | `X-Shopify-Hmac-Sha256` | `X-Shopify-Topic` |
| Slack | `X-Slack-Signature` | Included in JSON payload (`type`) |
| Twilio | `X-Twilio-Signature` | Form-encoded parameters |

## Automatic HMAC Webhook Resigning

When you edit a webhook payload before replaying it, standard HMAC signatures become invalid, causing verification libraries (like `stripe-python` or `@octokit/webhooks`) to reject the payload.

EdgePort solves this by calculating fresh cryptographic signatures when replaying modified payloads:

- **Stripe**: recomputes `v1` SHA-256 HMAC and updates the timestamp `t` to the current system time.
- **GitHub**: recomputes `sha256=` HMAC hash across the new body bytes.
- **Shopify**: recomputes Base64-encoded SHA-256 HMAC digest.

You can provide your signing secret via the **Edit & Replay** modal in the web dashboard or programmatically via the ReplayEngine.

## Built-in Mock Webhook Generator

Generate and send realistic, signed webhooks directly from the CLI without needing access to production dashboards:

```bash
# Send a Stripe payment_intent.succeeded event
edgeport mock stripe payment_intent.succeeded --target http://localhost:8080/webhooks --secret whsec_test_secret

# Send a GitHub push event
edgeport mock github push --target http://localhost:8080/webhooks --secret github_secret

# Send a Shopify order creation event
edgeport mock shopify orders/create --target http://localhost:8080/webhooks --secret shopify_secret

# List all available mock templates
edgeport mock --list
```

## Workflow: Developing Webhook Consumers

1. Start your local application on port 3000:
   ```bash
   npm run dev
   ```

2. Expose the port with EdgePort:
   ```bash
   edgeport expose 3000 --subdomain pay-test --notify
   ```

3. Configure your webhook URL in the provider dashboard:
   ```text
   http://pay-test.yourrelay.com/api/webhooks
   ```

4. Trigger a test event from the provider. EdgePort intercepts the request and forwards it to `http://localhost:3000/api/webhooks`.

5. If your local code throws an error or returns a 500 status:
   - Fix the bug in your code.
   - Press `r` in the EdgePort terminal TUI, or click Replay in the web dashboard at `http://localhost:4040`.
   - EdgePort resends the exact captured headers and payload to your local endpoint.
   - You can repeat this replay loop until your handler returns 200 OK.

6. Export the captured traffic to HAR 1.2 or Postman Collection v2.1 for integration testing:
   ```bash
   edgeport export --format postman --output test_webhooks.json
   ```

## Standalone Mock Sink Mode

If you do not have a local backend server running yet and want to observe the exact payload structure sent by an external provider, run EdgePort in sink mode:

```bash
edgeport sink --port 8080 --subdomain webhook-test
```

The mock sink:
- Listens on the specified local port.
- Connects to the relay and exposes `webhook-test`.
- Automatically responds to any incoming HTTP request with `200 OK`.
- Pretty-prints the request path, headers, and parsed body directly in your terminal.
