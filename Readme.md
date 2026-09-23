2 Labs
curl -i 'http://127.0.0.1:8000/shipments?status=created'

curl -i -X PATCH http://127.0.0.1:8000/shipments/shipment-001 \
-H 'Content-Type: application/json' -d '{"order_id":order-1}'

http://127.0.0.1:8000/docs