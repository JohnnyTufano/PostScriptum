from typing import List
from pydantic import BaseModel, Field


class Materiale(BaseModel):
    nome: str = Field(description="Nome del materiale o oggetto di scena")


class Costume(BaseModel):
    personaggio: str = Field(description="Nome del personaggio a cui appartiene il costume")
    descrizione: str = Field(description="Descrizione dell'abito o accessorio")


class Personaggio(BaseModel):
    nome: str = Field(description="Nome del personaggio, in MAIUSCOLO come nello script")
    descrizione: str = Field(default="", description="Descrizione breve del personaggio")
    costume: Costume = Field(default_factory=lambda: Costume(personaggio="", descrizione=""))
    materiali: List[Materiale] = Field(default_factory=list, description="Oggetti personali del personaggio")


class Location(BaseModel):
    nome: str = Field(description="Nome della location (es. Ristorante, Strada)")
    descrizione: str = Field(default="", description="Descrizione della location")
    materiali: List[Materiale] = Field(default_factory=list, description="Arredi/oggetti necessari")


class Scene(BaseModel):
    nome: str = Field(description="Numero e intestazione della scena, es. '12. INT. CUCINA - GIORNO'")
    descrizione: str = Field(default="", description="Riassunto breve della scena")
    materiali: List[Materiale] = Field(default_factory=list, description="Oggetti di scena usati nella scena")
    costumi: List[Costume] = Field(default_factory=list, description="Costumi indossati nella scena")
    locations: List[Location] = Field(default_factory=list)


class Sceneggiatura(BaseModel):
    titolo: str = Field(description="Titolo della sceneggiatura")
    descrizione: str = Field(default="", description="Sinossi")
    scene: List[Scene] = Field(default_factory=list)
    personaggi: List[Personaggio] = Field(default_factory=list)
    locations: List[Location] = Field(default_factory=list)


class AnalisiBlocco(BaseModel):
    """Schema che Gemini deve restituire per UN blocco di scene."""
    scene: List[Scene] = Field(default_factory=list)
    personaggi: List[Personaggio] = Field(default_factory=list)