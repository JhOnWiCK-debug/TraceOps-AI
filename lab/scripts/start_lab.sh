#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAB_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

mkdir -p "$LAB_DIR/logs" "$LAB_DIR/data"

python "$LAB_DIR/services/redis/redis_mock.py" > "$LAB_DIR/logs/redis_mock.out" 2>&1 &
REDIS_PID=$!

python "$LAB_DIR/services/payment/app.py" > "$LAB_DIR/logs/payment.out" 2>&1 &
PAYMENT_PID=$!

python "$LAB_DIR/services/checkout/app.py" > "$LAB_DIR/logs/checkout.out" 2>&1 &
CHECKOUT_PID=$!

printf 'Started:\n'
printf '  Redis mock PID: %s\n' "$REDIS_PID"
printf '  Payment service PID: %s\n' "$PAYMENT_PID"
printf '  Checkout service PID: %s\n' "$CHECKOUT_PID"
printf '\nUse: python %s/scripts/generate_requests.py --count 30 --interval 0.5\n' "$LAB_DIR"
printf 'Use: python %s/scripts/fault_injector.py --action fail\n' "$LAB_DIR"
printf 'Use: python %s/scripts/fault_injector.py --action recover\n' "$LAB_DIR"
