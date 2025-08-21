from pydantic import BaseModel, Field


class FoursquareSearchParams(BaseModel):
    query: str = Field(description="The core search keyword, e.g. 'burger', 'pizza', etc.")
    open_now: bool | None = Field(default=None, description="Whether to filter for places open now")
    radius: int | None = Field(default=None, description="Radius in meters (if specified)")
    limit: int | None = Field(default=None, description="Number of results to return")
    fsq_category_ids: str | None = Field(default=None, description="Foursquare category IDs, comma-separated if multiple")
    min_price: int | None = Field(default=None, description="Minimum price (1=most affordable, 4=most expensive)")
    max_price: int | None = Field(default=None, description="Maximum price (1=most affordable, 4=most expensive)")
    search_now: bool = Field(default=False, description="True if the user wants to trigger the search now, otherwise False.")
    explanation: str = Field(description="Explanation of how the query was parsed")


class UserInputClassifier(BaseModel):
    is_valid: bool = Field(description="Checks if the overall user_input is correct or not")
    phone: str = Field(description="The phone number extracted from user input")
    website: str = Field(description="The website extracted from user input")
    email: str = Field(description="The email extracted from user input")
    facebookUrl: str = Field(default="", description="Facebook page URL if provided")
    instagram: str = Field(default="", description="Instagram handle or URL if provided")
    twitter: str = Field(default="", description="Twitter/X handle or URL if provided")
    explanation: str = Field(default="", description="Explanation for the response you provide")


class AddressParseResult(BaseModel):
    is_valid: bool = Field(description="Whether the address could be parsed confidently")
    address: str = Field(default="", description="Street address or first line")
    locality: str = Field(default="", description="City or locality")
    region: str = Field(default="", description="State or province")
    postcode: str = Field(default="", description="Postal/ZIP code")
    countryCode: str = Field(default="", description="2-letter country code, e.g. US, IN")
    explanation: str = Field(default="", description="Short explanation if parsing failed or assumptions made") 