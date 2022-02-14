from __future__ import annotations
import logging
import re
from abc import ABC, abstractmethod
from typing import Sequence

from home_connect_async import Appliance, Events
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class EntityBase(ABC):
    """Base class with common methods for all the entities """

    should_poll = False
    _appliance: Appliance = None

    def __init__(self, appliance:Appliance, key:str=None, conf:dict=None) -> None:
        """Initialize the sensor."""
        self._appliance = appliance
        self._key = key
        self._conf = conf if conf else {}
        self.entity_id = f'home_connect.{self.unique_id}'

    @property
    def haId(self) -> str:
        """ The haID of the appliance """
        return self._appliance.haId.lower().replace('-','_')


    @property
    def device_info(self):
        """Return information to link this entity with the correct device."""
        return {
            "identifiers": {(DOMAIN, self.haId)},
            "name": self._appliance.name,
            "manufacturer": self._appliance.brand,
            "model": self._appliance.vib,
        }

    @property
    def device_class(self) -> str:
        """ Return the device class, if defined """
        if self._conf:
            return self._conf.get('class')
        else:
            return None

    @property
    def unique_id(self) -> str:
        """" The unique ID oif the entity """
        return f"{self.haId}_{self._key.lower().replace('.','_')}"

    @property
    def name_ext(self) -> str|None:
        return None

    @property
    def name(self) -> str:
        """" The name of the entity """
        appliance_name = self._appliance.name if self._appliance.name else self._appliance.type
        name = self.name_ext if self.name_ext else self.pretty_enum(self._key)
        return f"{self._appliance.brand} {appliance_name} - {name}"

    # This property is important to let HA know if this entity is online or not.
    # If an entity is offline (return False), the UI will refelect this.
    @property
    def available(self) -> bool:
        """ Avilability of the enity """
        return self._appliance.connected


    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        events = [Events.CONNECTION_CHANGED, Events.DATA_CHANGED]
        if self._key:
            events.append(self._key)
        self._appliance.register_callback(self.async_on_update, events)

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        events = [Events.CONNECTION_CHANGED, Events.DATA_CHANGED]
        if self._key:
            events.append(self._key)
        self._appliance.deregister_callback(self.async_on_update, events)

    @abstractmethod
    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        pass

    def pretty_enum(self, val:str) -> str:
        """ Extract display string from a Home COnnect Enum string """
        name = val.split('.')[-1]
        parts = re.findall('[A-Z0-9]+[^A-Z]*', name)
        return' '.join(parts)



class EntityManager():
    """ Helper class for managing entity registration

    Dupliaction might happen because there is a race condition between the task that
    loads data from the Home Connect service and the initialization of the platforms.
    This class prevents that from happening

    """
    def __init__(self, async_add_entities:AddEntitiesCallback):
        self._existing_ids = set()
        self._pending_entities:dict[str, Entity] = {}
        self._entity_appliance_map = {}
        self._async_add_entities = async_add_entities

    def add(self, entity:Entity) -> None:
        """ Add a new entiity unless it already esists """
        if entity and (entity.unique_id not in self._existing_ids) and (entity.unique_id not in self._pending_entities):
            self._pending_entities[entity.unique_id] = entity

    def register(self) -> None:
        """ register the pending entities with Home Assistant """
        new_ids = set(self._pending_entities.keys())
        new_entities = list(self._pending_entities.values())
        for entity in new_entities:
            if entity.haId not in self._entity_appliance_map:
                self._entity_appliance_map[entity.haId] = set()
            self._entity_appliance_map[entity.haId].add(entity.unique_id)
        self._async_add_entities(new_entities)
        self._existing_ids |= new_ids
        self._pending_entities = {}

    # def register_entities(self, entities:Sequence[Entity], async_add_entities:AddEntitiesCallback):
    #     """ Register new entities making sure they are only added once """
    #     ids = set([ ent.unique_id for ent in entities])
    #     for entity in entities:
    #         if entity.haId not in self._entity_appliance_map:
    #             self._entity_appliance_map[entity.haId] = set()
    #         self._entity_appliance_map[entity.haId].add(entity.unique_id)
    #     new_ids = ids - (ids & self._existing_ids)
    #     new_entities = [ entity for entity in entities if entity.unique_id in new_ids ]
    #     for e in new_entities:
    #         _LOGGER.debug("New entity: %s (%s)", e.name, e.unique_id)
    #     async_add_entities(new_entities)
    #     self._existing_ids |= new_ids

    def remove_appliance(self, appliance:Appliance):
        """ Remove an appliance and all its registered entities """
        if appliance.haId in self._entity_appliance_map:
            self._existing_ids -= self._entity_appliance_map[appliance.haId]
            del self._entity_appliance_map[appliance.haId]



# def clean_existing_entities(hass:HomeAssistant, entities:Sequence) -> Sequence :
#     """ Helper function to make sure the same entioty is not added twice """
#     ids = [ ent.unique_id for ent in entities]
#     ent_reg = er.async_get(hass)
#     resolved = er.async_resolve_entity_ids(ent_reg, ids)

