"""HTTP status code schemas for test assertions."""

from http import HTTPStatus

from d42 import schema

OkStatusSchema = schema.int(HTTPStatus.OK)
CreatedStatusSchema = schema.int(HTTPStatus.CREATED)
AcceptedStatusSchema = schema.int(HTTPStatus.ACCEPTED)
NoContentStatusSchema = schema.int(HTTPStatus.NO_CONTENT)
BadRequestStatusSchema = schema.int(HTTPStatus.BAD_REQUEST)
UnauthorizedStatusSchema = schema.int(HTTPStatus.UNAUTHORIZED)
ForbiddenStatusSchema = schema.int(HTTPStatus.FORBIDDEN)
NotFoundStatusSchema = schema.int(HTTPStatus.NOT_FOUND)
ConflictStatusSchema = schema.int(HTTPStatus.CONFLICT)
UnprocessableEntityStatusSchema = schema.int(HTTPStatus.UNPROCESSABLE_ENTITY)
InternalServerErrorStatusSchema = schema.int(HTTPStatus.INTERNAL_SERVER_ERROR)
ServiceUnavailableStatusSchema = schema.int(HTTPStatus.SERVICE_UNAVAILABLE)

__all__ = [
    "AcceptedStatusSchema",
    "BadRequestStatusSchema",
    "ConflictStatusSchema",
    "CreatedStatusSchema",
    "ForbiddenStatusSchema",
    "InternalServerErrorStatusSchema",
    "NoContentStatusSchema",
    "NotFoundStatusSchema",
    "OkStatusSchema",
    "ServiceUnavailableStatusSchema",
    "UnauthorizedStatusSchema",
    "UnprocessableEntityStatusSchema",
]
