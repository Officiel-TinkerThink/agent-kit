# sec-01 spec

Flask endpoints for a lab information service: sample search by site, report download by id, and a generic upload download route.
Intent: analysts search samples at their site and download the reports they own.
Uploads are stored under the lab upload root; the health route is used by the load balancer.
