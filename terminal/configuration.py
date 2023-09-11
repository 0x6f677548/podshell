from uuid import uuid4


class TerminalProfile:
    '''A terminal profile.'''

    def __init__(self,
                 name: str,
                 commandline: str):
        self.name = name
        self.commandline = commandline
        self.guid = f"{{{uuid4()}}}"

    def __str__(self):
        return f"TerminalProfile(name={self.name}, commandline={self.commandline}, guid={self.guid})"


class BaseConfiguration:
    '''Base class for terminal configurations. This class should not be used directly.'''

    def add_profile(self, profile: TerminalProfile, group_name: str = None) -> None:
        '''Add a profile to the configuration. If group_name is not None, the profile will be added to the group.'''
        self.add_profiles([profile], group_name)

    def add_profiles(self, profiles: list[TerminalProfile], group_name: str = None) -> None:
        '''Adds profiles to the configuration. If group_name is not None, the profiles will be added to the group.'''
        pass

    def remove_profile(self, profile_name: str) -> None:
        '''Remove a profile from the configuration.'''
        self.remove_profiles([profile_name])

    def remove_profiles(self, profile_names: list[str]) -> None:
        '''Remove a list of profiles from the configuration.'''
        pass

    def remove_group(self, group_name: str) -> None:
        '''Remove a group from the configuration.'''
        pass

    def backup(self) -> None:
        '''Backup the configuration.'''
        pass
