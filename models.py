from typing import List
from pydantic import BaseModel, Field

class Materiale(BaseModel):
    nome: str = Field(description="Nome del materiale o oggetto di scena")

class Costume(BaseModel):
    personaggio: str = Field(description="Nome del personaggio a cui appartiene il costume")
    descrizione: str = Field(description="Descrizione dell'abito o accessorio")

class Personaggio(BaseModel):
    nome: str = Field(description="Nome del personaggio")
    descrizione: str = Field(default="", description="Descrizione del personaggio")
    costume: Costume = Field(default_factory=lambda: Costume(personaggio="", descrizione=""))
    materiali: List[Materiale] = Field(default_factory=list)

class Location(BaseModel):
    nome: str = Field(description="Nome della location (es. Ristorante, Strada)")
    descrizione: str = Field(default="", description="Descrizione della location")
    materiali: List[Materiale] = Field(default_factory=list)

class Scene(BaseModel):
    nome: str = Field(description="Nome o numero della scena")
    descrizione: str = Field(default="", description="Descrizione generale della scena")
    materiali: List[Materiale] = Field(default_factory=list)
    costumi: List[Costume] = Field(default_factory=list)
    locations: List[Location] = Field(default_factory=list)

class Sceneggiatura(BaseModel):
    titolo: str = Field(description="Titolo della sceneggiatura")
    descrizione: str = Field(default="", description="Descrizione o sinossi della sceneggiatura")
    scene: List[Scene] = Field(default_factory=list)
    personaggi: List[Personaggio] = Field(default_factory=list)