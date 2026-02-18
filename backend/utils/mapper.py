from utils.dtos import EstimatorResponseDTO, EstimatorResultDTO, EstimatorItemDTO, ApiResponseMetaDTO

def map_to_estimator_dto(api_json) -> EstimatorResponseDTO:
    
    meta = api_json["result"]["response"]

    response_meta_dto = ApiResponseMetaDTO(
        status=meta["status"],
        statusCode=meta["statusCode"],
        message=meta["message"],
        description=meta["description"],
        traceId=meta.get("traceId")
    )

    items_dto = [
        EstimatorItemDTO(
            name=item["name"],
            typeIdentifier=item["typeIdentifier"],
            identifier=item["identifier"],
            image=item["image"]
        )
        for item in api_json["result"]["data"]
    ]

    result_dto = EstimatorResultDTO(
        response=response_meta_dto,
        data=items_dto
    )

    return EstimatorResponseDTO(result=result_dto)
