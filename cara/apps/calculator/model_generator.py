from dataclasses import dataclass
import html
import logging
import typing

import numpy as np

from cara import models
from cara import data


LOG = logging.getLogger(__name__)


minutes_since_midnight = typing.NewType('minutes_since_midnight', int)
@dataclass
class FormData:
    activity_type: str
    air_changes: float
    air_supply: float
    ceiling_height: float
    exposed_coffee_break_option: str
    exposed_coffee_duration: int
    exposed_finish: minutes_since_midnight
    exposed_lunch_finish: minutes_since_midnight
    exposed_lunch_option: bool
    exposed_lunch_start: minutes_since_midnight
    exposed_start: minutes_since_midnight
    floor_area: float
    hepa_amount: float
    hepa_option: bool
    infected_coffee_break_option: str               #Used if infected_dont_have_breaks_with_exposed
    infected_coffee_duration: int                   #Used if infected_dont_have_breaks_with_exposed
    infected_dont_have_breaks_with_exposed: bool
    infected_finish: minutes_since_midnight
    infected_lunch_finish: minutes_since_midnight   #Used if infected_dont_have_breaks_with_exposed
    infected_lunch_option: bool                     #Used if infected_dont_have_breaks_with_exposed
    infected_lunch_start: minutes_since_midnight    #Used if infected_dont_have_breaks_with_exposed
    infected_people: int
    infected_start: minutes_since_midnight
    mask_type: str
    mask_wearing_option: str
    mechanical_ventilation_type: str
    model_version: str
    opening_distance: float
    event_month: str
    room_number: str
    room_volume: float
    simulation_name: str
    total_people: int
    ventilation_type: str
    virus_type: str
    volume_type: str
    windows_duration: float
    windows_frequency: float
    window_height: float
    window_type: str
    window_width: float
    windows_number: int
    window_opening_regime: str

    @classmethod
    def from_dict(cls, form_data: typing.Dict) -> "FormData":
        # Take a copy of the form data so that we can mutate it.
        form_data = form_data.copy()

        valid_na_values = ['window_opening_regime', 'window_type', 'mechanical_ventilation_type', 'infected_dont_have_breaks_with_exposed']
        for name in valid_na_values:
            if not form_data.get(name, ''):
                form_data[name] = 'not-applicable'

        for name in ['exposed_lunch_start', 'exposed_lunch_finish', 'infected_lunch_start', 'infected_lunch_finish']:
            if not form_data.get(name, ''):
                form_data[name] = '00:00'

        # Don't let arbitrary unescaped HTML through the net.
        for key, value in form_data.items():
            if isinstance(value, str):
                form_data[key] = html.escape(value)

        # TODO: This fixup is a problem with the form.html.
        for key, value in form_data.items():
            if value == "":
                form_data[key] = "0"

        for attr_name in BOOLEAN_ATTRIBUTES:
            form_data[attr_name] = form_data[attr_name] == '1'
        for attr_name in FLOAT_ATTRIBUTES:
            form_data[attr_name] = float(form_data[attr_name])
        for attr_name in INT_ATTRIBUTES:
            form_data[attr_name] = int(form_data[attr_name])
        for attr_name in TIME_ATTRIBUTES:
            form_data[attr_name] = time_string_to_minutes(form_data[attr_name])

        form_data.pop('_xsrf', None)
        instance = cls(**form_data)
        instance.validate()
        return instance

    @classmethod
    def to_dict(self, form: "FormData") -> dict:
        form_dict = form.__dict__.copy()
        for attr_name in TIME_ATTRIBUTES:
            form_dict[attr_name] = time_minutes_to_string(form_dict[attr_name])
        for attr_name in BOOLEAN_ATTRIBUTES:
            form_dict[attr_name] = form_dict[attr_name] & 1
        return form_dict

    def validate(self):
        # Validate time intervals selected by user
        time_intervals = [
            ['exposed_start', 'exposed_finish'],
            ['infected_start', 'infected_finish'],
        ]
        if self.exposed_lunch_option:
            time_intervals.append(['exposed_lunch_start', 'exposed_lunch_finish'])
        if self.infected_dont_have_breaks_with_exposed and self.infected_lunch_option:
            time_intervals.append(['infected_lunch_start', 'infected_lunch_finish'])

        for start_name, end_name in time_intervals:
            start = getattr(self, start_name)
            end = getattr(self, end_name)
            if start > end:
                raise ValueError(
                    f"{start_name} must be less than {end_name}. Got {start} and {end}.")

        validation_tuples = [('activity_type', ACTIVITY_TYPES),    
                             ('exposed_coffee_break_option', COFFEE_OPTIONS_INT), 
                             ('infected_coffee_break_option', COFFEE_OPTIONS_INT),   
                             ('mechanical_ventilation_type', MECHANICAL_VENTILATION_TYPES),
                             ('mask_type', MASK_TYPES),
                             ('mask_wearing_option', MASK_WEARING_OPTIONS),
                             ('ventilation_type', VENTILATION_TYPES),
                             ('virus_type', VIRUS_TYPES),
                             ('volume_type', VOLUME_TYPES),
                             ('window_opening_regime', WINDOWS_OPENING_REGIMES),
                             ('window_type', WINDOWS_TYPES)]
        for attr_name, valid_set in validation_tuples:
            if getattr(self, attr_name) not in valid_set:
                raise ValueError(f"{getattr(self, attr_name)} is not a valid value for {attr_name}")

        if (
                self.ventilation_type == 'natural'
                and self.window_type == 'not-applicable'
        ):
            raise ValueError("window_type cannot be 'not-applicable' if "
                             "ventilation_type is 'natural'")

    def build_model(self) -> models.ExposureModel:
        return model_from_form(self)

    def ventilation(self) -> models._VentilationBase:
        always_on = models.PeriodicInterval(period=120, duration=120)
        # Initializes a ventilation instance as a window if 'natural_ventilation' is selected, or as a HEPA-filter otherwise
        if self.ventilation_type == 'natural_ventilation':
            if self.window_opening_regime == 'windows_open_periodically':
                window_interval = models.PeriodicInterval(self.windows_frequency, self.windows_duration)
            else:
                window_interval = always_on

            month = self.event_month[:3]

            inside_temp = models.PiecewiseConstant((0, 24), (293,))
            outside_temp = data.GenevaTemperatures[month]

            ventilation: models.Ventilation
            if self.window_type == 'window_sliding':
                ventilation = models.SlidingWindow(
                    active=window_interval,
                    inside_temp=inside_temp,
                    outside_temp=outside_temp,
                    window_height=self.window_height,
                    opening_length=self.opening_distance,
                    number_of_windows=self.windows_number,
                )
            elif self.window_type == 'window_hinged':
                ventilation = models.HingedWindow(
                    active=window_interval,
                    inside_temp=inside_temp,
                    outside_temp=outside_temp,
                    window_height=self.window_height,
                    window_width=self.window_width,
                    opening_length=self.opening_distance,
                    number_of_windows=self.windows_number,
                )

        elif self.ventilation_type == "no_ventilation":
            ventilation = models.AirChange(active=always_on, air_exch=0.)
        else:
            if self.mechanical_ventilation_type == 'mech_type_air_changes':
                ventilation = models.AirChange(active=always_on, air_exch=self.air_changes)
            else:
                ventilation = models.HVACMechanical(
                    active=always_on, q_air_mech=self.air_supply)

        if self.hepa_option:
            hepa = models.HEPAFilter(active=always_on, q_air_mech=self.hepa_amount)
            return models.MultipleVentilation((ventilation, hepa))
        else:
            return ventilation

    def mask(self) -> models.Mask:
        # Initializes the mask type if mask wearing is "continuous", otherwise instantiates the mask attribute as
        # the "No mask"-mask
        mask = models.Mask.types[self.mask_type if self.mask_wearing_option == "mask_on" else 'No mask']
        return mask

    def infected_population(self) -> models.InfectedPopulation:
        # Initializes the virus
        virus = models.Virus.types[self.virus_type]

        scenario_activity_and_expiration = {
            'office': (
                'Seated',
                # Mostly silent in the office, but 1/3rd of time talking.
                {'Talking': 1, 'Breathing': 2}
            ),
            'controlroom-day': (
                'Seated',
                # Daytime control room shift, 50% talking.
                {'Talking': 1, 'Breathing': 1}
            ),
            'controlroom-night': (
                'Seated',
                # Nightshift control room, 10% talking.
                {'Talking': 1, 'Breathing': 9}
            ),
            'meeting': (
                'Seated',
                # Conversation of N people is approximately 1/N% of the time talking.
                {'Talking': 1, 'Breathing': self.total_people - 1}
            ),
            'callcentre': ('Seated', 'Talking'),
            'library': ('Seated', 'Breathing'),
            'training': ('Standing', 'Talking'),
            'lab': (
                'Light activity',
                #Model 1/2 of time spent talking in a lab.
                {'Talking': 1, 'Breathing': 1}),
            'workshop': (
                'Moderate activity',
                #Model 1/2 of time spent talking in a workshop.
                {'Talking': 1, 'Breathing': 1}),
            'gym':('Heavy exercise', 'Breathing'),
        }

        [activity_defn, expiration_defn] = scenario_activity_and_expiration[self.activity_type]
        activity = models.Activity.types[activity_defn]
        expiration = build_expiration(expiration_defn)

        infected_occupants = self.infected_people

        infected = models.InfectedPopulation(
            number=infected_occupants,
            virus=virus,
            presence=self.infected_present_interval(),
            mask=self.mask(),
            activity=activity,
            expiration=expiration
        )
        return infected

    def exposed_population(self) -> models.Population:
        scenario_activity = {
            'office': 'Seated',
            'controlroom-day': 'Seated',
            'controlroom-night': 'Seated',
            'meeting': 'Seated',
            'callcentre': 'Seated',
            'library': 'Seated',
            'training': 'Seated',
            'workshop': 'Moderate activity',
            'lab':'Light activity',
            'gym':'Heavy exercise',
        }

        activity_defn = scenario_activity[self.activity_type]
        activity = models.Activity.types[activity_defn]

        infected_occupants = self.infected_people
        # The number of exposed occupants is the total number of occupants
        # minus the number of infected occupants.
        exposed_occupants = self.total_people - infected_occupants

        exposed = models.Population(
            number=exposed_occupants,
            presence=self.exposed_present_interval(),
            activity=activity,
            mask=self.mask(),
        )
        return exposed

    def _compute_breaks_in_interval(self, start, finish, n_breaks, duration) -> models.BoundarySequence_t:
        break_delay = ((finish - start) - (n_breaks * duration)) // (n_breaks+1)
        break_times = []
        end = start
        for n in range(n_breaks):
            begin = end + break_delay
            end = begin + duration
            break_times.append((begin, end))
        return tuple(break_times)

    def exposed_lunch_break_times(self) -> models.BoundarySequence_t:
        result = []
        if self.exposed_lunch_option:
            result.append((self.exposed_lunch_start, self.exposed_lunch_finish))
        return tuple(result)

    def infected_lunch_break_times(self) -> models.BoundarySequence_t:
        if self.infected_dont_have_breaks_with_exposed:
            result = []
            if self.infected_lunch_option:
                result.append((self.infected_lunch_start, self.infected_lunch_finish))
            return tuple(result)
        else:
            return self.exposed_lunch_break_times()

    def exposed_number_of_coffee_breaks(self) -> int:
        return COFFEE_OPTIONS_INT[self.exposed_coffee_break_option]

    def infected_number_of_coffee_breaks(self) -> int:
        return COFFEE_OPTIONS_INT[self.infected_coffee_break_option]

    def _coffee_break_times(self, activity_start, activity_finish, coffee_breaks, coffee_duration, lunch_start, lunch_finish) -> models.BoundarySequence_t:
        time_before_lunch = lunch_start - activity_start
        time_after_lunch = activity_finish - lunch_finish
        before_lunch_frac = time_before_lunch / (time_before_lunch + time_after_lunch)
        n_morning_breaks = round(coffee_breaks * before_lunch_frac)
        breaks = (
            self._compute_breaks_in_interval(
                activity_start, lunch_start, n_morning_breaks, coffee_duration
            )
            + self._compute_breaks_in_interval(
                lunch_finish, activity_finish, coffee_breaks - n_morning_breaks, coffee_duration
            )
        )
        return breaks

    def exposed_coffee_break_times(self) -> models.BoundarySequence_t:
        exposed_coffee_breaks = self.exposed_number_of_coffee_breaks()
        if exposed_coffee_breaks == 0:
            return ()
        if self.exposed_lunch_option:
            breaks = self._coffee_break_times(self.exposed_start, self.exposed_finish, exposed_coffee_breaks, self.exposed_coffee_duration, self.exposed_lunch_start, self.exposed_lunch_finish)
        else:
            breaks = self._compute_breaks_in_interval(self.exposed_start, self.exposed_finish, exposed_coffee_breaks, self.exposed_coffee_duration)
        return breaks

    def infected_coffee_break_times(self) -> models.BoundarySequence_t:
        if self.infected_dont_have_breaks_with_exposed:
            infected_coffee_breaks = self.infected_number_of_coffee_breaks()
            if infected_coffee_breaks == 0:
                return ()
            if self.infected_lunch_option:
                breaks = self._coffee_break_times(self.infected_start, self.infected_finish, infected_coffee_breaks, self.infected_coffee_duration, self.infected_lunch_start, self.infected_lunch_finish)
            else:
                breaks = self._compute_breaks_in_interval(self.infected_start, self.infected_finish, infected_coffee_breaks, self.infected_coffee_duration)
            return breaks
        else:
            return self.exposed_coffee_break_times()

    def present_interval(
            self,
            start: int,
            finish: int,
            breaks: typing.Optional[models.BoundarySequence_t] = None,
    ) -> models.Interval:
        """
        Calculate the presence interval given the start and end times (in minutes), and
        a number of monotonic, non-overlapping, but potentially unsorted, breaks (also in minutes).

        """
        if not breaks:
            # If there are no breaks, the interval is the start and end.
            return models.SpecificInterval(((start/60, finish/60),))

        # Order the breaks by their start-time, and ensure that they are monotonic
        # and that the start of one break happens after the end of another.
        break_boundaries: models.BoundarySequence_t = tuple(sorted(breaks, key=lambda break_pair: break_pair[0]))

        for break_start, break_end in break_boundaries:
            if break_start >= break_end:
                raise ValueError("Break ends before it begins.")

        prev_break_end = break_boundaries[0][1]
        for break_start, break_end in break_boundaries[1:]:
            if prev_break_end >= break_start:
                raise ValueError(f"A break starts before another ends ({break_start}, {break_end}, {prev_break_end}).")
            prev_break_end = break_end

        present_intervals = []

        def hours2time(hours: float):
            # Convert times like 14.5 to strings, like "14:30"
            return f"{int(np.floor(hours)):02d}:{int(np.round((hours % 1) * 60)):02d}"

        # def add_interval(start, end):

        current_time = start
        LOG.debug(f"starting time march at {hours2time(current_time/60)} to {hours2time(finish/60)}")

        # As we step through the breaks. For each break there are 6 important cases
        # we must cover. Let S=start; E=end; Bs=Break start; Be=Break end:
        #  1. The interval is entirely before the break. S < E <= Bs < Be
        #  2. The interval straddles the start of the break. S < Bs < E <= Be
        #  3. The break is entirely inside the interval. S < Bs < Be <= E
        #  4. The interval is entirely inside the break. Bs <= S < E <= Be
        #  5. The interval straddles the end of the break. Bs <= S < Be <= E
        #  6. The interval is entirely after the break. Bs < Be <= S < E

        for current_break in break_boundaries:
            if current_time >= finish:
                break

            LOG.debug(f"handling break {hours2time(current_break[0]/60)}-{hours2time(current_break[1]/60)} "
                      f" (current time: {hours2time(current_time/60)})")

            break_s, break_e = current_break
            case1 = finish <= break_s
            case2 = current_time < break_s < finish < break_e
            case3 = current_time < break_s < break_e <= finish
            case4 = break_s <= current_time < finish <= break_e
            case5 = break_s <= current_time < break_e < finish
            case6 = break_e <= current_time

            if case1:
                LOG.debug(f"case 1: interval entirely before break")
                present_intervals.append((current_time / 60, finish / 60))
                LOG.debug(f" + added interval {hours2time(present_intervals[-1][0])} "
                          f"- {hours2time(present_intervals[-1][1])}")
                current_time = finish
            elif case2:
                LOG.debug(f"case 2: interval straddles start of break")
                present_intervals.append((current_time / 60, break_s / 60))
                LOG.debug(f" + added interval {hours2time(present_intervals[-1][0])} "
                          f"- {hours2time(present_intervals[-1][1])}")
                current_time = break_e
            elif case3:
                LOG.debug(f"case 3: break entirely inside interval")
                # We add the bit before the break, but not the bit afterwards,
                # as it may hit another break.
                present_intervals.append((current_time / 60, break_s / 60))
                LOG.debug(f" + added interval {hours2time(present_intervals[-1][0])} "
                          f"- {hours2time(present_intervals[-1][1])}")
                current_time = break_e
            elif case4:
                LOG.debug(f"case 4: interval entirely inside break")
                current_time = finish
            elif case5:
                LOG.debug(f"case 5: interval straddles end of break")
                current_time = break_e
            elif case6:
                LOG.debug(f"case 6: interval entirely after the break")

        if current_time < finish:
            LOG.debug("trailing interval")
            present_intervals.append((current_time / 60, finish / 60))

        return models.SpecificInterval(tuple(present_intervals))

    def infected_present_interval(self) -> models.Interval:
        return self.present_interval(
            self.infected_start, self.infected_finish,
            breaks=self.infected_lunch_break_times() + self.infected_coffee_break_times(),
        )

    def exposed_present_interval(self) -> models.Interval:
        return self.present_interval(
            self.exposed_start, self.exposed_finish,
            breaks=self.exposed_lunch_break_times() + self.exposed_coffee_break_times(),
        )


def build_expiration(expiration_definition) -> models.Expiration:
    if isinstance(expiration_definition, str):
        return models.Expiration.types[expiration_definition]
    elif isinstance(expiration_definition, dict):
        return expiration_blend({
            build_expiration(exp): amount
            for exp, amount in expiration_definition.items()
            }
        )


def expiration_blend(expiration_weights: typing.Dict[models.Expiration, int]) -> models.Expiration:
    """
    Combine together multiple types of Expiration, using a weighted mean to
    compute their ejection factor and particle sizes.

    """
    ejection_factor = np.zeros(4)
    particle_sizes = np.zeros(4)

    total_weight = 0
    for expiration, weight in expiration_weights.items():
        total_weight += weight
        ejection_factor += np.array(expiration.ejection_factor) * weight
        particle_sizes += np.array(expiration.particle_sizes) * weight

    r_ejection_factor: typing.Tuple[float, float, float, float] = tuple(ejection_factor/total_weight)  # type: ignore
    r_particle_sizes: typing.Tuple[float, float, float, float] = tuple(particle_sizes/total_weight)  # type: ignore

    return models.Expiration(ejection_factor=r_ejection_factor, particle_sizes=r_particle_sizes)


def model_from_form(form: FormData) -> models.ExposureModel:
    # Initializes room with volume either given directly or as product of area and height
    if form.volume_type == 'room_volume_explicit':
        volume = form.room_volume
    else:
        volume = form.floor_area * form.ceiling_height
    room = models.Room(volume=volume)

    # Initializes and returns a model with the attributes defined above
    return models.ExposureModel(
        concentration_model=models.ConcentrationModel(
            room=room,
            ventilation=form.ventilation(),
            infected=form.infected_population(),
        ),
        exposed=form.exposed_population()
    )


def baseline_raw_form_data():
    # Note: This isn't a special "baseline". It can be updated as required.
    return {
        'activity_type': 'office',
        'air_changes': '',
        'air_supply': '',
        'ceiling_height': '',
        'exposed_coffee_break_option': 'coffee_break_4',
        'exposed_coffee_duration': '10',
        'exposed_finish': '18:00',
        'exposed_lunch_finish': '13:30',
        'exposed_lunch_option': '1',
        'exposed_lunch_start': '12:30',
        'exposed_start': '09:00',
        'floor_area': '',
        'hepa_amount': '250',
        'hepa_option': '0',
        'infected_coffee_break_option': 'coffee_break_4',
        'infected_coffee_duration': '10',
        'infected_dont_have_breaks_with_exposed': '1',
        'infected_finish': '18:00',
        'infected_lunch_finish': '13:30',
        'infected_lunch_option': '1',
        'infected_lunch_start': '12:30',
        'infected_people': '1',
        'infected_start': '09:00',
        'mask_type': 'Type I',
        'mask_wearing_option': 'mask_off',
        'mechanical_ventilation_type': '',
        'model_version': 'v1.2.0',
        'opening_distance': '0.2',
        'event_month': 'January',
        'room_number': '123',
        'room_volume': '75',
        'simulation_name': 'Test',
        'total_people': '10',
        'ventilation_type': 'natural_ventilation',
        'virus_type': 'SARS_CoV_2',
        'volume_type': 'room_volume_explicit',
        'windows_duration': '',
        'windows_frequency': '',
        'window_height': '2',
        'window_type': 'window_sliding',
        'window_width': '2',
        'windows_number': '1',
        'window_opening_regime': 'windows_open_permanently'
    }


ACTIVITY_TYPES = {'office', 'meeting', 'training', 'callcentre', 'controlroom-day', 'controlroom-night', 'library', 'workshop', 'lab', 'gym'}
MECHANICAL_VENTILATION_TYPES = {'mech_type_air_changes', 'mech_type_air_supply', 'not-applicable'}
MASK_TYPES = {'Type I', 'FFP2'}
MASK_WEARING_OPTIONS = {'mask_on', 'mask_off'}
VENTILATION_TYPES = {'natural_ventilation', 'mechanical_ventilation', 'no_ventilation'}
VIRUS_TYPES = {'SARS_CoV_2', 'SARS_CoV_2_B117', 'SARS_CoV_2_P1'}
VOLUME_TYPES = {'room_volume_explicit', 'room_volume_from_dimensions'}
WINDOWS_OPENING_REGIMES = {'windows_open_permanently', 'windows_open_periodically', 'not-applicable'}
WINDOWS_TYPES = {'window_sliding', 'window_hinged', 'not-applicable'}

COFFEE_OPTIONS_INT = {'coffee_break_0':0, 'coffee_break_1':1, 'coffee_break_2':2, 'coffee_break_4':4}

BOOLEAN_ATTRIBUTES = {'hepa_option', 'exposed_lunch_option', 'infected_lunch_option', 'infected_dont_have_breaks_with_exposed'}
FLOAT_ATTRIBUTES = {'air_changes', 'air_supply', 'ceiling_height', 'floor_area', 'hepa_amount', 'opening_distance', 
        'room_volume', 'windows_duration', 'windows_frequency', 'window_height', 'window_width'}
INT_ATTRIBUTES = {'exposed_coffee_duration', 'infected_coffee_duration', 'infected_people', 'total_people', 'windows_number'}
TIME_ATTRIBUTES = {'exposed_lunch_start', 'exposed_lunch_finish', 'exposed_start', 'exposed_finish',
                'infected_lunch_start', 'infected_lunch_finish', 'infected_start', 'infected_finish'}        

def time_string_to_minutes(time: str) -> minutes_since_midnight:
    """
    Converts time from string-format to an integer number of minutes after 00:00
    :param time: A string of the form "HH:MM" representing a time of day
    :return: The number of minutes between 'time' and 00:00
    """
    return minutes_since_midnight(60 * int(time[:2]) + int(time[3:]))

def time_minutes_to_string(time: int) -> str:
    """
    Converts time from an integer number of minutes after 00:00 to string-format
    :param time: The number of minutes between 'time' and 00:00
    :return: A string of the form "HH:MM" representing a time of day
    """
    return "{0:0=2d}".format(int(time/60)) + ":" + "{0:0=2d}".format(time%60)
