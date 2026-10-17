# Partner order listing and export: intent

Partners read their orders through the partner API. They need two things: a list of orders that can be narrowed to one status, and a text export of orders with a fixed column set that partners already import. The export keeps its current column order. Business logic stays in the service layer so that the same filtering and export rules can be reused by other callers.
