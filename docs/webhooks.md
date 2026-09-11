# Webhook Inspection and Replay

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

## Workflow: Developing Webhook Consumers

1. Start your local application on port 3000:
   ```bash
   npm run dev
   ```

2. Expose the port with EdgePort:
   ```bash
   edgeport expose 3000 --subdomain pay-test
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
